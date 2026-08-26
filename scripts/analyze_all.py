"""Turn every harvested subreddit into an honest name. Resumable."""
import atexit, json, os, pathlib, sys, time, traceback
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.signals import profile
from honest_sub.sheet import render
from honest_sub.name import name_subreddit
from honest_sub.llm import LMStudio
from honest_sub.corpus import completed, path_for, targets_meta

GAPS = pathlib.Path("data/meta/gap_scores.json")

LOCK = pathlib.Path("data/out/.analyze.lock")
OUT = pathlib.Path("data/out"); OUT.mkdir(parents=True, exist_ok=True)


def acquire_lock() -> None:
    """Refuse to start if another run holds the lock.

    Two concurrent runs append to the same results file and duplicate every
    model call, so this is a hard stop rather than a warning.
    """
    if LOCK.exists():
        try:
            pid = int(LOCK.read_text().strip())
        except (ValueError, OSError):
            pid = None
        if pid is not None:
            try:
                os.kill(pid, 0)
            except OSError:
                pass  # stale lock from a killed run
            else:
                sys.exit(f"analyze_all.py already running as pid {pid}; "
                         f"remove {LOCK} if that is wrong")
    LOCK.write_text(str(os.getpid()))
    atexit.register(lambda: LOCK.unlink(missing_ok=True))
SHEETS = pathlib.Path("data/sheets"); SHEETS.mkdir(parents=True, exist_ok=True)
RESULTS = OUT / "honest_names.jsonl"


def main():
    acquire_lock()
    subs = completed()
    meta = targets_meta()
    print(f"profiling {len(subs)} subreddits…", flush=True)

    profs = {}
    for i, s in enumerate(subs, 1):
        profs[s] = profile(path_for(s))
        if i % 20 == 0:
            print(f"  profiled {i}/{len(subs)}", flush=True)

    # Background for the log-odds baseline: the pooled vocabulary of every sub
    # in the set, so "distinctive" means distinctive *among large subreddits*
    # rather than distinctive versus English at large.
    bg = Counter()
    for p in profs.values():
        bg.update(p["kept_words"])
    print(f"background vocabulary: {len(bg):,} types\n", flush=True)

    done = set()
    if RESULTS.exists():
        for ln in RESULTS.read_text().splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            # rows that errored are left out of `done` so they get retried
            if "subreddit" in r and not r.get("error"):
                done.add(r["subreddit"])

    gaps = {}
    if GAPS.exists():
        gaps = {g["subreddit"]: g for g in json.load(open(GAPS))}
    else:
        print("WARNING: no gap_scores.json; run scripts/score_gaps.py first",
              file=sys.stderr)

    lm = LMStudio()
    todo = [s for s in subs if s not in done]
    print(f"{len(done)} already named, {len(todo)} to go\n", flush=True)

    with open(RESULTS, "a") as fh:
        for i, s in enumerate(todo, 1):
            sheet = render(s, meta.get(s, {}), profs[s], bg)
            (SHEETS / f"{s}.md").write_text(sheet)
            t0 = time.time()
            try:
                r = name_subreddit(lm, sheet)
                g = gaps.get(s, {})
                r.update(subreddit=s, subscribers=meta.get(s, {}).get("subscribers"),
                         posts=profs[s]["posts"],
                         mod_removal_rate=profs[s]["mod_removal_rate"],
                         # measured, not asked of the model
                         gap_severity=g.get("gap_severity", "unrated"),
                         gap_score=g.get("gap_score"),
                         identity_match=g.get("identity_match"),
                         seconds=round(time.time() - t0, 1))
            except Exception as e:
                traceback.print_exc()
                r = {"subreddit": s, "error": f"{type(e).__name__}: {e}"}
            fh.write(json.dumps(r, ensure_ascii=False) + "\n"); fh.flush()
            tag = r.get("honest_name", "ERROR")
            sev = r.get("gap_severity", "?")
            print(f"[{i}/{len(todo)}] r/{s:24} [{sev:8}] → {tag}  "
                  f"({r.get('seconds','?')}s)", flush=True)


if __name__ == "__main__":
    main()
