"""Crowd co-activity: what share of a sub's posters also post in political subs?

For each half-year, sample the sub's distinct authors and ask (one API call
per author) where else they posted THAT half-year. Membership in an explicit,
disclosed set of political subreddits makes an author "politically co-active".
The measure only means something as an EXCESS over a genre-matched baseline
sub, since Reddit-wide politicization lifts every raw share.

Title-independent by construction: it detects a political crowd moving in even
when every caption stays neutral -- the failure mode of text metrics on image
subs. Resumable per (sub, bucket, author).
"""
import argparse, datetime as dt, json, pathlib, random, sys, time
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.arctic import ArcticShift
from honest_sub.harvest import read_posts

POLITICAL = {"politics", "conservative", "democrats", "libertarian",
             "politicalhumor", "worldpolitics", "political_revolution",
             "conspiracy", "publicfreakout"}
SUBS = ["pics", "aww"]
PER_BUCKET = 80
OUT = pathlib.Path("data/out/crowd_coactivity.jsonl")
BOTS = {"AutoModerator", "PicsMod", "[deleted]"}


def corpora(sub):
    for d in ("data/raw_hist", "data/raw", "data/raw_deep"):
        p = pathlib.Path(d) / f"{sub}.posts.jsonl.zst"
        if p.exists():
            yield p


def buckets(sub):
    seen = {}
    for f in corpora(sub):
        for p in read_posts(f):
            seen[p["id"]] = p
    by = defaultdict(set)
    for p in seen.values():
        a = p.get("author")
        if not a or a in BOTS or a.endswith("Bot") or a.endswith("bot"):
            continue
        d = dt.datetime.fromtimestamp(p["created_utc"], dt.timezone.utc)
        by[(d.year, 1 if d.month <= 6 else 2)].add(a)
    return by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-bucket", type=int, default=PER_BUCKET,
                    help="authors per half-year; the shuffle is seeded, so a larger "
                         "run extends the earlier sample rather than redrawing it")
    ap.add_argument("--since", default="2008H1", help="first bucket, e.g. 2023H1")
    args = ap.parse_args()
    api = ArcticShift(min_interval=0.42)
    done = set()
    if OUT.exists():
        for ln in OUT.read_text().splitlines():
            if ln.strip():
                r = json.loads(ln)
                done.add((r["sub"], r["bucket"], r["author"]))
    with open(OUT, "a") as fh:
        for sub in SUBS:
            by = buckets(sub)
            todo_total = 0
            for (y, h) in sorted(by):
                if f"{y}H{h}" < args.since:
                    continue
                authors = sorted(by[(y, h)])
                rng = random.Random(f"{sub}-{y}-{h}")
                rng.shuffle(authors)
                sample = authors[:args.per_bucket]
                start = int(dt.datetime(y, 1 if h == 1 else 7, 1,
                                        tzinfo=dt.timezone.utc).timestamp())
                end = int(dt.datetime(y + (h == 2), 7 if h == 1 else 1, 1,
                                      tzinfo=dt.timezone.utc).timestamp())
                pend = [a for a in sample if (sub, f"{y}H{h}", a) not in done]
                todo_total += len(pend)
                for a in pend:
                    try:
                        ps = api._get("/api/posts/search", author=a, after=start,
                                      before=end, limit=100, fields="subreddit")
                    except Exception as e:
                        print(f"  !! {a}: {type(e).__name__}", flush=True)
                        continue
                    subs_hit = {(x.get("subreddit") or "").lower() for x in (ps or [])}
                    fh.write(json.dumps({"sub": sub, "bucket": f"{y}H{h}", "author": a,
                                         "political": bool(subs_hit & POLITICAL),
                                         "hit": sorted(subs_hit & POLITICAL),
                                         "n_posts": len(ps or [])}) + "\n")
                fh.flush()
                print(f"r/{sub} {y}H{h}: bucket done", flush=True)
            print(f"r/{sub}: complete ({todo_total} new checks)", flush=True)
    print("crowd_run done", flush=True)


if __name__ == "__main__":
    main()
