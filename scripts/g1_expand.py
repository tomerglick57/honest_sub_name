"""Grow r/Conservative's left-advocacy survivor sample to close G1.

Classifies a survivors-only random sample -- kept posts carry all the yield for
the vote test, so a case-control draw would waste half the GPU on removed
posts. These labels live in SEPARATE files (…survivors.jsonl) and must never
enter the moderation odds ratio: they are not a case-control sample.
"""
import argparse, atexit, json, os, pathlib, random, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.harvest import read_posts
from honest_sub.llm import LMStudio
from honest_sub.slant import classify_batch
from honest_sub.quote import classify_batch_quote

SUB = "Conservative"
MAN = pathlib.Path("data/out/slant_manifests/Conservative.survivors.json")
ST_OUT = pathlib.Path("data/out/slant_labels/Conservative.survivors.jsonl")
Q_OUT = pathlib.Path("data/out/q_labels/Conservative.survivors.jsonl")
LOCK = pathlib.Path("data/out/.g1x.lock")
BATCH = 12


def lock():
    if LOCK.exists():
        try:
            os.kill(int(LOCK.read_text().strip()), 0)
        except (OSError, ValueError):
            pass
        else:
            sys.exit("g1_expand already running")
    LOCK.write_text(str(os.getpid()))
    atexit.register(lambda: LOCK.unlink(missing_ok=True))


def manifest():
    if MAN.exists():
        return json.loads(MAN.read_text())
    already = set()
    for f in (pathlib.Path("data/out/slant_labels/Conservative.jsonl"),):
        for ln in f.read_text().splitlines():
            r = json.loads(ln)
            if r.get("id"):
                already.add(r["id"])
    posts = read_posts(pathlib.Path("data/raw_deep/Conservative.posts.jsonl.zst"))
    pool = [{"id": p["id"], "title": p["title"]} for p in posts
            if not p.get("removed_by_category") and (p.get("title") or "").strip()
            and p["id"] not in already]
    random.Random(1).shuffle(pool)
    sample = pool[:6000]
    MAN.write_text(json.dumps(sample))
    print(f"survivors manifest: {len(sample)} of {len(pool)} unlabeled survivors", flush=True)
    return sample


def read_ids(path):
    out = {}
    if path.exists():
        for ln in path.read_text().splitlines():
            if ln.strip():
                r = json.loads(ln)
                out[r["id"]] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", type=int, required=True)
    ap.add_argument("--limit", type=int, default=4600)
    args = ap.parse_args()
    lock()
    lm = LMStudio()
    man = manifest()
    done = read_ids(ST_OUT)
    todo = [m for m in man if m["id"] not in done][:args.limit]
    print(f"stance pass: {len(done)} done, {len(todo)} to go", flush=True)
    t0 = time.time()
    failed = 0
    with open(ST_OUT, "a") as fh:
        for i in range(0, len(todo), BATCH):
            if time.time() > args.deadline - 300:
                print("deadline: stopping stance pass", flush=True)
                break
            chunk = todo[i:i + BATCH]
            try:
                labs = classify_batch(lm, [c["title"] for c in chunk], "us_politics")
            except Exception as e:
                failed += 1
                print(f"  !! batch failed ({type(e).__name__})", flush=True)
                if failed > 40:
                    break
                continue
            for c, l in zip(chunk, labs):
                fh.write(json.dumps({"id": c["id"], "title": c["title"],
                                     "label": l}, ensure_ascii=False) + "\n")
            fh.flush()
            if (i // BATCH) % 10 == 0:
                print(f"  {i+len(chunk)}/{len(todo)}  {time.time()-t0:.0f}s", flush=True)

    # Q-pass every newly A- or B-labelled survivor (A is the scarce side G1
    # needs; B costs little and keeps the two pools methodologically identical)
    st = read_ids(ST_OUT)
    qdone = read_ids(Q_OUT)
    qtodo = [r for r in st.values() if r["label"] in ("A", "B") and r["id"] not in qdone]
    print(f"q pass: {len(qtodo)} sided survivors to label", flush=True)
    with open(Q_OUT, "a") as fh:
        for i in range(0, len(qtodo), BATCH):
            if time.time() > args.deadline - 240:
                print("deadline: stopping q pass", flush=True)
                break
            chunk = qtodo[i:i + BATCH]
            try:
                labs = classify_batch_quote(lm, [c["title"] for c in chunk])
            except Exception:
                continue
            for c, l in zip(chunk, labs):
                fh.write(json.dumps({"id": c["id"], "q": l}) + "\n")
            fh.flush()
    print("g1_expand done", flush=True)


if __name__ == "__main__":
    main()
