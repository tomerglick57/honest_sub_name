"""Validate the fast front-page labels against the same model WITH reasoning.

Production labels (honest_sub.topic) run with reasoning disabled for 4x
throughput. This re-labels a stratified random sample of front-page posts
with reasoning on -- the configuration whose labels passed the project's
validation gates -- so the speed-up is measured rather than assumed. The
sample is stratified by production label and era, so the rare classes (L, R)
and the early years are actually tested, not drowned by the O majority.
"""
import concurrent.futures as cf, json, pathlib, random, sys, threading
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.frontpage import top_of_days
from honest_sub.harvest import read_posts
from honest_sub.llm import LMStudio, Truncated
from honest_sub.topic import SYSTEM, schema

SUB = "pics"
CDIR = pathlib.Path("data/census") / SUB
LABELS = pathlib.Path("data/out/frontpage") / f"{SUB}.labels.jsonl"
OUT = pathlib.Path("data/out/frontpage") / f"{SUB}.validate.jsonl"
PER_CELL, BATCH = 25, 12
era = lambda m: "2008-15" if m < "2016" else "2016-23" if m < "2024" else "2024-26"


def slow_labels(lm, titles):
    listing = "\n".join(f"{i}. {' '.join(t.split())[:220]}" for i, t in enumerate(titles))
    budget = 12000
    for attempt in range(3):
        try:
            out = lm.chat_json(SYSTEM, listing, schema(len(titles)), max_tokens=budget, temperature=0.6)
            return [out[str(i)] for i in range(len(titles))]
        except (Truncated, json.JSONDecodeError):
            budget *= 2
    raise RuntimeError("reasoning pass kept truncating")


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def main():
    lab = {}
    for ln in LABELS.read_text().splitlines():
        try:
            r = json.loads(ln); lab[r["id"]] = r["label"]
        except (json.JSONDecodeError, KeyError):
            pass
    items = {}
    for f in sorted(CDIR.glob("*.jsonl.zst")):
        for ps in top_of_days(read_posts(f), 10).values():
            for p in ps:
                if p["id"] in lab:
                    items[p["id"]] = (p.get("title") or "", f.name[:7])
    cells = defaultdict(list)
    for i, (_, m) in items.items():
        cells[(era(m), lab[i])].append(i)
    rng = random.Random("validate-v1")
    pick = []
    for key in sorted(cells):
        ids = sorted(cells[key]); rng.shuffle(ids); pick += ids[:PER_CELL]
    done = {}
    if OUT.exists():
        for ln in OUT.read_text().splitlines():
            r = json.loads(ln); done[r["id"]] = r
    todo = [i for i in pick if i not in done]
    print(f"sample {len(pick)} ({len(todo)} to label) from cells "
          f"{ {f'{e}/{l}': min(len(v), PER_CELL) for (e, l), v in sorted(cells.items())} }", flush=True)
    lock, tls = threading.Lock(), threading.local()

    def work(chunk):
        if not hasattr(tls, "lm"):
            tls.lm = LMStudio()
        try:
            slow = slow_labels(tls.lm, [items[i][0] for i in chunk])
        except Exception as e:
            print(f"  !! {type(e).__name__}: {str(e)[:100]}", flush=True)
            return
        with lock, open(OUT, "a") as fh:
            for i, s in zip(chunk, slow):
                r = {"id": i, "month": items[i][1], "fast": lab[i], "slow": s}
                done[i] = r
                fh.write(json.dumps(r) + "\n")

    with cf.ThreadPoolExecutor(2) as ex:
        list(ex.map(work, [todo[k:k + BATCH] for k in range(0, len(todo), BATCH)]))

    rows = [done[i] for i in pick if i in done]
    pol = lambda l: "pol" if l != "O" else "O"
    print(f"\n{len(rows)} titles re-labeled with reasoning")
    for name, sel in [("all", rows)] + [(e, [r for r in rows if era(r["month"]) == e])
                                        for e in ("2008-15", "2016-23", "2024-26")]:
        if not sel:
            continue
        b = [(pol(r["fast"]), pol(r["slow"])) for r in sel]
        f4 = [(r["fast"], r["slow"]) for r in sel]
        print(f"{name:8s} n={len(sel):3d}  political-vs-not agree {sum(a == c for a, c in b) / len(b):.1%} "
              f"(kappa {kappa(b):.2f})  4-way {sum(a == c for a, c in f4) / len(f4):.1%} (kappa {kappa(f4):.2f})")
    print("confusion fast->slow:", Counter((r["fast"], r["slow"]) for r in rows).most_common())
    print("\ndisagreements on political-vs-not (for audit):")
    for r in [r for r in rows if pol(r["fast"]) != pol(r["slow"])][:12]:
        print(f"  {r['month']} fast={r['fast']} slow={r['slow']}  {items[r['id']][0][:110]}")


if __name__ == "__main__":
    main()
