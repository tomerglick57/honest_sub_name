"""M3 visitor control: was the author active in the sub BEFORE their post?

Distinguishes chilled regulars from drive-by visitors: a "didn't return"
from someone with no prior in-sub history is not attrition, it is a visitor
leaving. Return rates are re-stratified on this flag in the final analysis.
"""
import json, pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.arctic import ArcticShift
from honest_sub.harvest import read_posts

SRC = pathlib.Path("data/out/m3_attrition.jsonl")
OUT = pathlib.Path("data/out/m3_prior.jsonl")
LOOKBACK = 180 * 86400


def main():
    api = ArcticShift(min_interval=0.45)
    rows = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
    done = set()
    if OUT.exists():
        done = {(r["sub"], r["id"]) for r in
                (json.loads(l) for l in OUT.read_text().splitlines() if l.strip())}
    posts = {}
    for sub in ("Conservative", "conspiracy", "politics"):
        for p in read_posts(pathlib.Path(f"data/raw_deep/{sub}.posts.jsonl.zst")):
            posts[(sub, p["id"])] = p
    todo = [r for r in rows if (r["sub"], r["id"]) not in done
            and (r["sub"], r["id"]) in posts]
    print(f"{len(done)} done, {len(todo)} to check", flush=True)
    with open(OUT, "a") as fh:
        for n, r in enumerate(todo):
            p = posts[(r["sub"], r["id"])]
            a, t = p["author"], p["created_utc"]
            try:
                prior = api._get("/api/posts/search", author=a, subreddit=r["sub"],
                                 after=t - LOOKBACK, before=t - 1, limit=1, fields="id")
                if not prior:  # posts silent -> check comments before calling them a visitor
                    prior = api._get("/api/comments/search", author=a, subreddit=r["sub"],
                                     after=t - LOOKBACK, before=t - 1, limit=1, fields="id")
            except Exception as e:
                print(f"  !! {a}: {type(e).__name__}", flush=True)
                continue
            fh.write(json.dumps({"sub": r["sub"], "id": r["id"],
                                 "prior_active": bool(prior)}) + "\n")
            fh.flush()
            if n % 300 == 0:
                print(f"  {n}/{len(todo)}", flush=True)
    print("m3_prior done", flush=True)


if __name__ == "__main__":
    main()
