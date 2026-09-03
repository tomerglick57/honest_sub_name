"""Advocacy-vs-quotation pass over every sided stance label. Resumable, deadline-aware.

Validation gates the pass: below 14/16 on the pre-registered probe set the
classifier is unusable and this exits nonzero so the driver stops the batch.
"""
import argparse, atexit, json, os, pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.llm import LMStudio
from honest_sub.quote import classify_batch_quote, validate

OUT = pathlib.Path("data/out/q_labels")
MANIFESTS = pathlib.Path("data/out/slant_manifests")
SLANT = pathlib.Path("data/out/slant_labels")
LOCK = pathlib.Path("data/out/.qpass.lock")
VALID_MARK = OUT / ".validated"
SUBS = ["Conservative", "conspiracy", "politics"]  # Conservative first: it gates G1
BATCH = 12


def lock():
    if LOCK.exists():
        try:
            os.kill(int(LOCK.read_text().strip()), 0)
        except (OSError, ValueError):
            pass
        else:
            sys.exit(f"qpass already running as pid {LOCK.read_text().strip()}")
    LOCK.write_text(str(os.getpid()))
    atexit.register(lambda: LOCK.unlink(missing_ok=True))


def stance_labels(sub):
    man = json.loads((MANIFESTS / f"{sub}.json").read_text())
    by_title = {m["title"]: m["id"] for m in man}
    titles = {m["id"]: m["title"] for m in man}
    out = {}
    for ln in (SLANT / f"{sub}.jsonl").read_text().splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        pid = r.get("id") or by_title.get(r.get("title", ""))
        if pid:
            out[pid] = (r["label"], titles.get(pid) or r.get("title", ""))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", type=int, required=True, help="unix ts; stop classifying 5 min before")
    args = ap.parse_args()
    lock()
    OUT.mkdir(parents=True, exist_ok=True)
    lm = LMStudio()

    if not VALID_MARK.exists():
        score, misses = validate(lm)
        print(f"probe validation: {score}/16", flush=True)
        for t, want, got in misses:
            print(f"   miss: want {want} got {got} :: {t[:80]}", flush=True)
        if score < 14:
            print("VALIDATION FAILED -- quote pass unusable, aborting batch", flush=True)
            sys.exit(2)
        VALID_MARK.write_text(str(score))

    for sub in SUBS:
        st = stance_labels(sub)
        qfile = OUT / f"{sub}.jsonl"
        done = set()
        if qfile.exists():
            for ln in qfile.read_text().splitlines():
                if ln.strip():
                    done.add(json.loads(ln)["id"])
        todo = [(pid, title) for pid, (lab, title) in st.items()
                if lab in ("A", "B") and pid not in done and title]
        if not todo:
            print(f"r/{sub}: q-pass complete ({len(done)} done)", flush=True)
            continue
        print(f"r/{sub}: {len(done)} done, {len(todo)} sided titles to q-label", flush=True)
        t0, n0 = time.time(), 0
        failed = 0
        with open(qfile, "a") as fh:
            for i in range(0, len(todo), BATCH):
                if time.time() > args.deadline - 300:
                    print(f"deadline reached at {n0} new labels; stopping cleanly", flush=True)
                    return
                chunk = todo[i:i + BATCH]
                try:
                    labs = classify_batch_quote(lm, [t for _, t in chunk])
                except Exception as e:
                    failed += 1
                    print(f"   !! batch failed ({type(e).__name__}) -- skipping", flush=True)
                    if failed > 40:
                        print("   too many failures, stopping", flush=True)
                        return
                    continue
                for (pid, title), l in zip(chunk, labs):
                    fh.write(json.dumps({"id": pid, "q": l}, ensure_ascii=False) + "\n")
                fh.flush()
                n0 += len(chunk)
                if (i // BATCH) % 10 == 0:
                    print(f"   {n0}/{len(todo)}  {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
