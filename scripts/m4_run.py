"""M4: stance-label author-deleted posts (case-control vs the existing kept labels).

Self-deletion (`removed_by_category == "deleted"`) is a pile-on proxy. The rate
alone means nothing -- people delete for many reasons -- so the reportable
quantity is the stance-mix asymmetry of deleted vs kept posts, computed in
batch2_analysis.py against the already-labelled kept arm.
"""
import argparse, atexit, json, os, pathlib, random, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.harvest import read_posts
from honest_sub.llm import LMStudio
from honest_sub.slant import classify_batch

SUBS = ["PublicFreakout", "Conservative", "politics", "conspiracy"]
MAN_DIR = pathlib.Path("data/out/m4_manifests")
LOCK = pathlib.Path("data/out/.m4.lock")
BATCH, PER_SUB = 12, 350


def lock():
    if LOCK.exists():
        try:
            os.kill(int(LOCK.read_text().strip()), 0)
        except (OSError, ValueError):
            pass
        else:
            sys.exit("m4 already running")
    LOCK.write_text(str(os.getpid()))
    atexit.register(lambda: LOCK.unlink(missing_ok=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", type=int, required=True)
    args = ap.parse_args()
    lock()
    MAN_DIR.mkdir(parents=True, exist_ok=True)
    lm = LMStudio()
    for sub in SUBS:
        man_p = MAN_DIR / f"{sub}.json"
        if man_p.exists():
            man = json.loads(man_p.read_text())
        else:
            dele = [{"id": p["id"], "title": p["title"]}
                    for p in read_posts(pathlib.Path(f"data/raw_deep/{sub}.posts.jsonl.zst"))
                    if p.get("removed_by_category") == "deleted"
                    and (p.get("title") or "").strip()]
            random.Random(2).shuffle(dele)
            man = dele[:PER_SUB]
            man_p.write_text(json.dumps(man))
        out = pathlib.Path(f"data/out/slant_labels/{sub}.deleted.jsonl")
        done = set()
        if out.exists():
            done = {json.loads(l)["id"] for l in out.read_text().splitlines() if l.strip()}
        todo = [m for m in man if m["id"] not in done]
        print(f"r/{sub}: {len(done)} done, {len(todo)} deleted titles to label", flush=True)
        with open(out, "a") as fh:
            for i in range(0, len(todo), BATCH):
                if time.time() > args.deadline - 240:
                    print("deadline: stopping m4", flush=True)
                    return
                chunk = todo[i:i + BATCH]
                try:
                    labs = classify_batch(lm, [c["title"] for c in chunk], "us_politics")
                except Exception:
                    continue
                for c, l in zip(chunk, labs):
                    fh.write(json.dumps({"id": c["id"], "label": l},
                                        ensure_ascii=False) + "\n")
                fh.flush()
    print("m4 done", flush=True)


if __name__ == "__main__":
    main()
