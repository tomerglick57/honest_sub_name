"""Labels for the r/pics vote-asymmetry test: do voters treat the two sides
of surviving political submissions differently?

Sample: a seeded random K surviving (non-removed) submissions per month from
the census, all hours. Pass 1 labels every title O/P/L/R (honest_sub.topic).
Pass 2 runs the advocacy-vs-quotation classifier (honest_sub.quote) on the
sided ones, because a title can express a view it is showcasing to mock;
the vote test is run on advocacy posts only (methodology §10, G1). Pass 2
uses the fast settings only if they pass the pre-registered probe set
(>=14/16); otherwise it falls back to the validated reasoning settings.
Resumable by post id. Concurrency defaults to 2: the host is shared.
"""
import argparse, concurrent.futures as cf, json, pathlib, random, sys, threading, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.harvest import read_posts
from honest_sub.llm import LMStudio
from honest_sub.quote import PROBES, SYSTEM as QSYS, classify_batch_quote
from honest_sub.topic import label_batch, MODEL_TAG

OUT = pathlib.Path("data/out/vote_asym")
BATCH = 40


def qschema(n):
    return {"type": "object",
            "properties": {str(i): {"type": "string", "enum": ["ADV", "QUO", "UNC"]} for i in range(n)},
            "required": [str(i) for i in range(n)], "additionalProperties": False}


def quote_fast(lm, titles):
    listing = "\n".join(f"{i}. {' '.join((t or '').split())[:220]}" for i, t in enumerate(titles))
    out = lm.chat_json(QSYS, listing, qschema(len(titles)), max_tokens=3000,
                       temperature=0.0, extra={"reasoning_effort": "none"})
    return [out[str(i)] for i in range(len(titles))]


def load(path, key):
    d = {}
    for ln in path.read_text().splitlines() if path.exists() else []:
        try:
            r = json.loads(ln); d[r["id"]] = r[key]
        except (json.JSONDecodeError, KeyError):
            pass
    return d


def run(items, fn, out, key, conc, tag):
    lock, tls = threading.Lock(), threading.local()

    def work(chunk):
        if not hasattr(tls, "lm"):
            tls.lm = LMStudio()
        try:
            labs = fn(tls.lm, [c["title"] for c in chunk])
        except Exception as e:
            print(f"  !! {tag} batch: {type(e).__name__}: {str(e)[:120]}", flush=True)
            return 0
        with lock, open(out, "a") as fh:
            for c, l in zip(chunk, labs):
                fh.write(json.dumps({"id": c["id"], "month": c["month"], key: l, "m": MODEL_TAG}) + "\n")
        return len(chunk)

    t0, total = time.time(), 0
    chunks = [items[i:i + BATCH] for i in range(0, len(items), BATCH)]
    with cf.ThreadPoolExecutor(conc) as ex:
        for j, k in enumerate(ex.map(work, chunks), 1):
            total += k
            if j % 20 == 0:
                print(f"  {tag}: {total:,}/{len(items):,}  {total / (time.time() - t0) * 3600:,.0f}/hr", flush=True)
    print(f"  {tag} pass done: {total:,} labeled", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sub", nargs="?", default="pics")
    ap.add_argument("--start", default="2025-09")
    ap.add_argument("--end", default="2026-08", help="inclusive")
    ap.add_argument("--k", type=int, default=2500, help="surviving submissions per month")
    ap.add_argument("--concurrency", type=int, default=2)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    lab_p, q_p = OUT / f"{args.sub}.labels.jsonl", OUT / f"{args.sub}.quotes.jsonl"
    lab, quo = load(lab_p, "label"), load(q_p, "q")
    sample = []
    for f in sorted((pathlib.Path("data/census") / args.sub).glob("*.jsonl.zst")):
        m = f.name[:7]
        if not (args.start <= m <= args.end):
            continue
        surv = sorted((p for p in read_posts(f) if not p.get("removed_by_category")), key=lambda p: p["id"])
        rng = random.Random(f"{args.sub}-{m}-vote")
        sample += [{"id": p["id"], "month": m, "title": p.get("title") or ""}
                   for p in rng.sample(surv, min(args.k, len(surv)))]
    print(f"{len(sample):,} sampled survivors {args.start}..{args.end}; {len(lab):,} already labeled", flush=True)
    run([s for s in sample if s["id"] not in lab], label_batch, lab_p, "label", args.concurrency, "stance")
    lab = load(lab_p, "label")
    sided = [s for s in sample if lab.get(s["id"]) in ("L", "R") and s["id"] not in quo]
    lm = LMStudio()
    got = quote_fast(lm, [t for t, _ in PROBES[:8]]) + quote_fast(lm, [t for t, _ in PROBES[8:]])
    ok = sum(g == w for g, (_, w) in zip(got, PROBES))
    print(f"quote probe, fast settings: {ok}/16 -> {'fast' if ok >= 14 else 'reasoning'} pass", flush=True)
    fn = quote_fast if ok >= 14 else (lambda lm, ts: classify_batch_quote(lm, ts))
    run(sided, fn, q_p, "q", args.concurrency, "quote")
    print("vote_asym_label done", flush=True)


if __name__ == "__main__":
    main()
