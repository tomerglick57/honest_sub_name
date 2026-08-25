"""Harvest every target subreddit into data/raw/. Resumable: skips finished subs."""
import json, pathlib, sys, time, traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.arctic import ArcticShift
from honest_sub.harvest import harvest_subreddit

RAW = pathlib.Path("data/raw")
META = pathlib.Path("data/meta")
LOG = META / "harvest_log.jsonl"

YEARS_BACK, PER_YEAR, QUOTA = 3, 4, 400   # ~13 quarterly windows, ~5.2k posts/sub

def done_subs() -> set[str]:
    if not LOG.exists():
        return set()
    out = set()
    for ln in LOG.read_text().splitlines():
        try:
            r = json.loads(ln)
            if r.get("ok"):
                out.add(r["subreddit"])
        except json.JSONDecodeError:
            pass
    return out

def main():
    targets = json.load(open(META / "targets.json"))
    already = done_subs()
    api = ArcticShift(min_interval=0.4)
    todo = [t for t in targets if t["display_name"] not in already]
    print(f"{len(already)} done, {len(todo)} to go", flush=True)

    with open(LOG, "a") as log:
        for i, t in enumerate(todo, 1):
            name = t["display_name"]
            t0 = time.time()
            try:
                s = harvest_subreddit(api, name, RAW, years_back=YEARS_BACK,
                                      quota_per_window=QUOTA, per_year=PER_YEAR)
                rec = {"ok": True, "subreddit": name, "posts": s["posts"],
                       "bytes": s["bytes"], "seconds": round(time.time() - t0, 1),
                       "subscribers": t.get("subscribers")}
            except Exception as e:
                rec = {"ok": False, "subreddit": name, "error": f"{type(e).__name__}: {e}",
                       "seconds": round(time.time() - t0, 1)}
                traceback.print_exc()
            log.write(json.dumps(rec) + "\n"); log.flush()
            print(f"[{i}/{len(todo)}] {json.dumps(rec)}", flush=True)

if __name__ == "__main__":
    main()
