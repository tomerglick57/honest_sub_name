"""Trial: TypeSafe Jev against the r/pics front-page labels from gemma.

Same task as honest_sub.topic (O/P/L/R per title), asked one title per
request as a Choice question. Two sets are labeled:
  * the 261-title stratified validation set (scripts/frontpage_validate.py),
    where gemma was run both fast (production) and with reasoning ("slow",
    the configuration that passed the project's gates);
  * a seeded random --extra sample of front-page titles with production
    labels, for agreement at scale, flair recall, latency and cost.

Nothing here is ground truth: the reference is gemma-with-reasoning, itself
96% in agreement with production. Disagreements with BOTH gemma passes are
printed for a human to judge. Resumable: rows are appended per title.
"""
import argparse, concurrent.futures as cf, json, pathlib, random, statistics, sys, threading, time
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.frontpage import top_of_days
from honest_sub.harvest import read_posts
from honest_sub.typesafe import TypeSafe

SUB = "pics"
CDIR = pathlib.Path("data/census") / SUB
LABELS = pathlib.Path("data/out/frontpage") / f"{SUB}.labels.jsonl"
VALIDATE = pathlib.Path("data/out/frontpage") / f"{SUB}.validate.jsonl"
OUT = pathlib.Path("data/out/frontpage") / f"{SUB}.typesafe.jsonl"
era = lambda m: "2008-15" if m < "2016" else "2016-23" if m < "2024" else "2024-26"
pol = lambda l: "pol" if l != "O" else "O"

# The same rubric as honest_sub.topic.SYSTEM, split into the option map the
# Choice primitive wants (docs: use what/not_for when options get confused).
from honest_sub.topic_jev import QUESTION  # noqa: E402


def kappa(pairs):
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def agree(name, rows, ref):
    b = [(pol(r["jev"]), pol(r[ref])) for r in rows]
    f4 = [(r["jev"], r[ref]) for r in rows]
    return (f"{name:8s} n={len(rows):4d}  political-vs-not {sum(a == c for a, c in b) / len(b):6.1%} "
            f"(kappa {kappa(b):.2f})  4-way {sum(a == c for a, c in f4) / len(f4):6.1%} (kappa {kappa(f4):.2f})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", type=int, default=750, help="random front-page titles beyond the 261")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--model", default="jev-latest")
    a = ap.parse_args()

    lab = {}
    for ln in LABELS.read_text().splitlines():
        try:
            r = json.loads(ln); lab[r["id"]] = r["label"]
        except (json.JSONDecodeError, KeyError):
            pass
    slow = {}
    for ln in VALIDATE.read_text().splitlines():
        r = json.loads(ln); slow[r["id"]] = r["slow"]
    items = {}
    for f in sorted(CDIR.glob("*.jsonl.zst")):
        for ps in top_of_days(read_posts(f), 10).values():
            for p in ps:
                if p["id"] in lab:
                    items[p["id"]] = {"title": " ".join((p.get("title") or "").split())[:220],
                                      "month": f.name[:7],
                                      "flair": (p.get("link_flair_text") or "")}
    pick = [i for i in slow if i in items]
    rng = random.Random("typesafe-trial-v1")
    rest = sorted(i for i in items if i not in slow); rng.shuffle(rest)
    pick += rest[:a.extra]

    done = {}
    if OUT.exists():
        for ln in OUT.read_text().splitlines():
            r = json.loads(ln); done[r["id"]] = r
    todo = [i for i in pick if i not in done]
    ts = TypeSafe(model=a.model)
    print(f"models: {[m.get('name') or m.get('id') for m in ts.models().get('models', [])]}")
    print(f"{len(pick)} titles ({len(slow)} validation + {a.extra} random), {len(todo)} to label", flush=True)
    lock, t0, n_done = threading.Lock(), time.time(), [0]

    def work(i):
        it = items[i]
        t = time.time()
        try:
            resp = ts.ask(it["title"], QUESTION)
        except Exception as e:
            print(f"  !! {i}: {type(e).__name__}: {str(e)[:120]}", flush=True)
            return
        ans = resp["answers"]["label"]
        r = {"id": i, "month": it["month"], "title": it["title"], "flair": it["flair"],
             "fast": lab[i], "slow": slow.get(i), "jev": ans["choice"],
             "conf": round(ans.get("confidence", 0), 4),
             "p": {k: round(v, 4) for k, v in ans.get("probabilities", {}).items()},
             "ms": int((time.time() - t) * 1000), "usage": resp.get("usage"), "m": resp.get("model")}
        with lock, open(OUT, "a") as fh:
            done[i] = r; fh.write(json.dumps(r) + "\n"); n_done[0] += 1
            if n_done[0] % 100 == 0:
                print(f"  {n_done[0]} labeled, {n_done[0] / (time.time() - t0):.1f}/s", flush=True)

    with cf.ThreadPoolExecutor(a.concurrency) as ex:
        list(ex.map(work, todo))
    wall = time.time() - t0

    rows = [done[i] for i in pick if i in done]
    val = [r for r in rows if r["slow"]]
    print(f"\n== {len(rows)} titles labeled by {rows[0]['m'] if rows else '?'}"
          + (f"; this run {len(todo)} in {wall:.0f}s at {a.concurrency} concurrent" if todo else ""))
    toks = [r["usage"]["input_tokens"] for r in rows if r.get("usage")]
    ms = sorted(r["ms"] for r in rows)
    if toks:
        print(f"input tokens/title mean {statistics.mean(toks):.0f}; cost per 1k titles "
              f"${statistics.mean(toks) * 0.042 / 1e3:.3f}; all {len(lab):,} production labels "
              f"${len(lab) * statistics.mean(toks) * 0.042 / 1e6:.2f}")
    print(f"latency ms p50 {ms[len(ms) // 2]} p90 {ms[int(len(ms) * .9)]} max {ms[-1]}")

    print("\n-- validation set: Jev vs gemma-with-reasoning (reference) and vs production fast")
    print(agree("vs slow", val, "slow"))
    print(agree("vs fast", val, "fast"))
    b = [(pol(r["fast"]), pol(r["slow"])) for r in val]; f4 = [(r["fast"], r["slow"]) for r in val]
    print(f"{'fast/slow':8s} n={len(val):4d}  political-vs-not {sum(a == c for a, c in b) / len(b):6.1%} "
          f"(kappa {kappa(b):.2f})  4-way {sum(a == c for a, c in f4) / len(f4):6.1%} (kappa {kappa(f4):.2f})"
          "   <- gemma's own fast-vs-reasoning agreement, same rows")
    for e in ("2008-15", "2016-23", "2024-26"):
        sel = [r for r in val if era(r["month"]) == e]
        if sel:
            print(agree(e, sel, "slow"))
    print("confusion jev->slow:", Counter((r["jev"], r["slow"]) for r in val).most_common())

    print("\n-- all rows: Jev vs production fast labels")
    print(agree("all", rows, "fast"))
    for e in ("2008-15", "2016-23", "2024-26"):
        sel = [r for r in rows if era(r["month"]) == e]
        if sel:
            print(agree(e, sel, "fast"))
    print("label mix  fast:", dict(Counter(r["fast"] for r in rows)), " jev:", dict(Counter(r["jev"] for r in rows)))
    fl = [r for r in rows if "politic" in r["flair"].lower()]
    if fl:
        print(f"flair recall (mod flair says political): jev {sum(r['jev'] != 'O' for r in fl)}/{len(fl)}"
              f"  fast {sum(r['fast'] != 'O' for r in fl)}/{len(fl)}")

    print("\n-- confidence: agreement with production by Jev confidence bin")
    bins = defaultdict(list)
    for r in rows:
        bins[min(int(r["conf"] * 5), 4)].append(r["jev"] == r["fast"])
    for k in sorted(bins):
        v = bins[k]
        print(f"  conf {k / 5:.1f}-{(k + 1) / 5:.1f}: n={len(v):4d} agree {sum(v) / len(v):.1%}")

    print("\n-- Jev disagrees with BOTH gemma passes on political-vs-not (for a human to judge):")
    for r in [r for r in val if pol(r["jev"]) != pol(r["slow"]) and pol(r["jev"]) != pol(r["fast"])][:20]:
        print(f"  {r['month']} jev={r['jev']} ({r['conf']:.2f}) gemma={r['fast']}/{r['slow']}  {r['title'][:105]}")
    print("\n-- Jev disagrees with BOTH on the L/R side (for a human to judge):")
    for r in [r for r in val if r["jev"] in "LR" and r["slow"] in "LR" and r["jev"] != r["slow"]
              and r["jev"] != r["fast"]][:20]:
        print(f"  {r['month']} jev={r['jev']} ({r['conf']:.2f}) gemma={r['fast']}/{r['slow']}  {r['title'][:105]}")


if __name__ == "__main__":
    main()
