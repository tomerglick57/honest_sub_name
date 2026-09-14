"""Subject-label every political front-page post of a sub (all eras).

Input: the census and the topic labels from frontpage_label.py; only posts
labeled P/L/R are sent. Output: data/out/frontpage/<sub>.subjects.jsonl,
resumable by id. Concurrency is a flag because the LAN host is shared.
"""
import argparse, concurrent.futures as cf, json, pathlib, sys, threading, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.frontpage import top_of_days
from honest_sub.harvest import read_posts
from honest_sub.llm import LMStudio
from honest_sub.subject import label_batch, MODEL_TAG

BATCH = 40


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sub", nargs="?", default="pics")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--concurrency", type=int, default=2)
    args = ap.parse_args()
    cdir = pathlib.Path("data/census") / args.sub
    labels = pathlib.Path("data/out/frontpage") / f"{args.sub}.labels.jsonl"
    out = pathlib.Path("data/out/frontpage") / f"{args.sub}.subjects.jsonl"
    lab = {}
    for ln in labels.read_text().splitlines():
        try:
            r = json.loads(ln); lab[r["id"]] = r["label"]
        except (json.JSONDecodeError, KeyError):
            pass
    done = set()
    if out.exists():
        for ln in out.read_text().splitlines():
            try:
                done.add(json.loads(ln)["id"])
            except (json.JSONDecodeError, KeyError):
                pass
    todo = []
    for f in sorted(cdir.glob("*.jsonl.zst")):
        for ps in top_of_days(read_posts(f), args.n).values():
            todo += [{"id": p["id"], "title": p.get("title") or ""} for p in ps
                     if lab.get(p["id"]) in ("P", "L", "R") and p["id"] not in done]
    print(f"{len(done)} done, {len(todo)} political front-page titles to label", flush=True)
    lock, tls = threading.Lock(), threading.local()

    def work(chunk):
        if not hasattr(tls, "lm"):
            tls.lm = LMStudio()
        try:
            labs = label_batch(tls.lm, [c["title"] for c in chunk])
        except Exception as e:
            print(f"  !! batch: {type(e).__name__}: {str(e)[:120]}", flush=True)
            return 0
        with lock, open(out, "a") as fh:
            for c, l in zip(chunk, labs):
                fh.write(json.dumps({"id": c["id"], "subject": l, "m": MODEL_TAG}) + "\n")
        return len(chunk)

    t0, total = time.time(), 0
    chunks = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    with cf.ThreadPoolExecutor(args.concurrency) as ex:
        for j, k in enumerate(ex.map(work, chunks), 1):
            total += k
            if j % 10 == 0:
                print(f"  {total:,}/{len(todo):,}  {total / (time.time() - t0) * 3600:,.0f}/hr", flush=True)
    print(f"subject_label r/{args.sub} done: {total:,} labeled", flush=True)


if __name__ == "__main__":
    main()
