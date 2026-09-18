"""Full census of a subreddit's posts, one file per month.

The stratified harvests in data/raw* take the FIRST N posts of each window
(`harvest_subreddit` walks ascending and breaks at the quota), so each sampled
window covers only the opening hours of a quarter -- New Year's Day, April 1st,
July 1st. Their "top decile" is the top of a few hundred early-morning posts,
not what a visitor saw. A day's front page is only knowable from every post of
that day, because the archive can neither sort nor filter by score. Hence a
census.

Output: data/census/<sub>/<YYYY-MM>.jsonl.zst. Each month is written as .part
and renamed when complete, so a crash never leaves a truncated month that looks
finished; rerunning skips completed months. Completeness is checked against
Arctic Shift's own monthly counts and logged. Months are visited in a strided
order (every 12th month first, then every 6th, ...) so a coarse picture of the
whole timeline exists early and sharpens as the run continues.
"""
import argparse, datetime as dt, json, pathlib, queue, sys, threading, time

import requests
import zstandard as zstd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.arctic import ArcticShift, BASE

KEEP = ("id", "created_utc", "title", "author", "score", "num_comments",
        "upvote_ratio", "link_flair_text", "domain", "url", "over_18",
        "removed_by_category", "locked", "stickied", "distinguished", "is_self",
        "num_crossposts", "selftext")
CAP = 300  # title/url/selftext characters; r/pics text is short, this bounds outliers


def project(p):
    out = {k: p.get(k) for k in KEEP}
    for k in ("title", "url", "selftext"):
        if out.get(k) and len(out[k]) > CAP:
            out[k] = out[k][:CAP]
    out["r2"] = (p.get("_meta") or {}).get("retrieved_2nd_on")
    return out


def month_bounds(y, m):
    s = dt.datetime(y, m, 1, tzinfo=dt.timezone.utc)
    e = dt.datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=dt.timezone.utc)
    return int(s.timestamp()), int(e.timestamp())


def strided(months):
    """Every 12th month, then every 6th, 3rd, then the rest: early coverage of the span."""
    order, seen = [], set()
    for step in (12, 6, 3, 1):
        for i in range(0, len(months), step):
            if i not in seen:
                seen.add(i); order.append(months[i])
    return order


def expected_counts(sub, tries=4):
    """The archive occasionally answers with an empty or HTML body; retry before giving up."""
    for attempt in range(tries):
        try:
            d = requests.get(f"{BASE}/api/time_series",
                             params={"key": f"r/{sub}/posts/count", "precision": "month"},
                             timeout=90).json()["data"]
            return {dt.datetime.fromtimestamp(x["date"], dt.timezone.utc).strftime("%Y-%m"): x["value"]
                    for x in d}
        except (requests.RequestException, ValueError, KeyError) as e:
            if attempt == tries - 1:
                raise
            print(f"  time_series failed ({type(e).__name__}); retrying in {15 * (attempt + 1)}s", flush=True)
            time.sleep(15 * (attempt + 1))


def walk_month(api, sub, start, end):
    posts, cursor, nreq = {}, start, 0
    while True:
        batch = api._get("/api/posts/search", subreddit=sub, after=cursor,
                         before=end, limit="auto", sort="asc")
        nreq += 1
        if not batch:
            return posts, nreq
        fresh = [p for p in batch if p["id"] not in posts]
        for p in fresh:
            posts[p["id"]] = project(p)
        last = batch[-1]["created_utc"]
        cursor = last if fresh else last + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sub", nargs="?", default="pics")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--interval", type=float, default=0.85,
                    help="min seconds between requests per worker (API asks for ~2 req/s)")
    ap.add_argument("--since", default="2005-01", help="first month to census (YYYY-MM)")
    args = ap.parse_args()

    out_dir = pathlib.Path("data/census") / args.sub
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_done.json").unlink(missing_ok=True)
    # _counts.json lists only the months in scope, so downstream completeness
    # checks (frontpage_label --follow) agree with what this run will produce
    exp = {k: v for k, v in expected_counts(args.sub).items() if k >= args.since}
    (out_dir / "_counts.json").write_text(json.dumps(exp, indent=0))
    today = dt.datetime.now(dt.timezone.utc)
    months = [k for k in sorted(exp) if exp[k] > 0 and k <= today.strftime("%Y-%m")]
    todo = [k for k in strided(months) if not (out_dir / f"{k}.jsonl.zst").exists()]
    print(f"r/{args.sub}: {len(months)} months, {len(todo)} to do, "
          f"~{sum(exp[k] for k in todo):,} posts expected", flush=True)

    q = queue.Queue()
    for k in todo:
        q.put(k)
    log_lock = threading.Lock()
    t0 = time.time()
    done_posts = [0]

    def worker():
        api = ArcticShift(min_interval=args.interval)
        while True:
            try:
                k = q.get_nowait()
            except queue.Empty:
                return
            y, m = map(int, k.split("-"))
            s, e = month_bounds(y, m)
            ts = time.time()
            try:
                posts, nreq = walk_month(api, args.sub, s, e)
            except Exception as ex:
                print(f"  !! {k}: {type(ex).__name__}: {ex} -- will retry on rerun", flush=True)
                continue
            part = out_dir / f"{k}.jsonl.zst.part"
            with open(part, "wb") as fh, zstd.ZstdCompressor(level=10).stream_writer(fh) as w:
                for p in sorted(posts.values(), key=lambda p: p["created_utc"]):
                    w.write((json.dumps(p, ensure_ascii=False) + "\n").encode())
            part.rename(out_dir / f"{k}.jsonl.zst")
            ratio = len(posts) / exp[k] if exp[k] else 0
            with log_lock:
                done_posts[0] += len(posts)
                rec = {"month": k, "n": len(posts), "expected": exp[k], "ratio": round(ratio, 4),
                       "requests": nreq, "secs": round(time.time() - ts, 1)}
                with open(out_dir / "_log.jsonl", "a") as lf:
                    lf.write(json.dumps(rec) + "\n")
                flag = "" if 0.97 <= ratio <= 1.03 else "  <-- CHECK"
                el = time.time() - t0
                print(f"{k}: {len(posts):>7,} / {exp[k]:>7,} ({ratio:.1%}) {nreq} req "
                      f"{rec['secs']:.0f}s | total {done_posts[0]:,} posts in {el/60:.0f} min{flag}",
                      flush=True)

    # Months that fail mid-walk (the archive's "Internal server error" comes in
    # bursts) are retried in later passes after a pause; a rerun picks up the rest.
    for pas in range(3):
        threads = [threading.Thread(target=worker) for _ in range(args.workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        missing = [k for k in months if not (out_dir / f"{k}.jsonl.zst").exists()]
        if not missing:
            break
        print(f"pass {pas + 1}: {len(missing)} months failed ({', '.join(missing[:6])}"
              f"{'...' if len(missing) > 6 else ''}); pausing 3 min before retrying", flush=True)
        time.sleep(180)
        for k in strided(missing):
            q.put(k)
    missing = [k for k in months if not (out_dir / f"{k}.jsonl.zst").exists()]
    # the marker lets followers (frontpage_label --follow) stop waiting even
    # when months are missing; it is removed at the start of the next run
    (out_dir / "_done.json").write_text(json.dumps({"finished": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
                                                     "missing": missing}))
    print(f"census r/{args.sub} done" + (f" with {len(missing)} months missing: {' '.join(missing)}" if missing else ""), flush=True)


if __name__ == "__main__":
    main()
