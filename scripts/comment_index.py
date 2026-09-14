"""Comment politicization index: share of ALL a sub's comments naming US
political actors, month by month -- counted server-side, nothing downloaded.

Arctic Shift's comment search takes full-text `body` queries with OR, and its
aggregate endpoint returns match counts. Summing matches over every window of
a month and dividing by the archive's own monthly comment count gives a
full-census rate over r/pics' ~125M comments. The server gives up at ~8 s on
heavy windows, so windows adapt: halve on timeout, double after fast replies.

Windows are whole UTC days, always. Measured 2026-09-12: for any window whose
`after` is not UTC-midnight-aligned, the aggregate endpoint answers HTTP 200
with zero-count buckets and no error. Halving windows by seconds produced such
windows and silently cut r/mildlyinteresting's January 2024 count from 1,533
to 154. `--verify K` recounts K months day by day to prove the totals.

Vocabulary (fixed, disclosed): presidents and major-party figures since 2008,
party and movement names, and unambiguous institutions. Deliberately excluded
for collisions in an image sub: bush (plants), sanders (KFC), vote (upvote
talk), president (company presidents), musk (Tesla-era, pre-political). It is
keyword matching: one name ('trump') absorbing discussion that earlier eras
spread across several is partly real salience and partly vocabulary, so read
it only against the baseline sub, which shares the same bias.
"""
import argparse, calendar, datetime as dt, json, pathlib, sys, time

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.arctic import BASE

TERMS = ["trump", "biden", "obama", "romney", "mccain", "palin", "hillary", "kamala",
         "bernie", "pelosi", "mcconnell", "desantis", "republican", "democrat", "gop",
         "maga", "fascist", "fascism", "congress", "senate", "election"]
QUERY = " OR ".join(TERMS)
DAY = 86400


class Timeout(Exception):
    pass


class Client:
    def __init__(self, interval):
        self.s, self.interval, self.last = requests.Session(), interval, 0.0
        self.s.headers["User-Agent"] = "honest-sub-name/0.1 (research; subreddit characterisation)"

    def get(self, path, **params):
        for attempt in range(6):
            gap = self.interval - (time.monotonic() - self.last)
            if gap > 0:
                time.sleep(gap)
            self.last = time.monotonic()
            try:
                r = self.s.get(f"{BASE}{path}", params=params, timeout=90)
                j = r.json()
            except (requests.RequestException, ValueError):
                time.sleep(5 * (attempt + 1)); continue
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1)); continue
            err = j.get("error")
            if err and "imeout" in err:
                raise Timeout(err)
            if err:
                raise RuntimeError(f"{params}: {err}")
            if j.get("data") is None:
                raise Timeout("null data without an error")
            return j["data"]
        raise RuntimeError(f"gave up: {path} {params}")


def monthly_totals(sub):
    d = requests.get(f"{BASE}/api/time_series",
                     params={"key": f"r/{sub}/comments/count", "precision": "month"},
                     timeout=90).json()["data"]
    return {dt.datetime.fromtimestamp(x["date"], dt.timezone.utc).strftime("%Y-%m"): x["value"]
            for x in d}


def count_piece(cli, sub, a, b):
    for k in range(3):
        try:
            data = cli.get("/api/comments/search/aggregate", subreddit=sub, body=QUERY,
                           aggregate="created_utc", frequency="hour", after=a, before=b)
            return sum(int(x["count"]) for x in data), k + 1
        except Timeout:
            time.sleep(8 * (k + 1))
    return None, 3


def day_by_hours(cli, sub, t):
    """One UTC day that times out whole, counted in hour-aligned pieces.

    Sub-day windows are safe only hour-aligned with frequency=hour: verified
    2026-09-12 that four 6-hour pieces sum exactly to the day's count
    (10+3+171+3 = 187). Pieces that still time out split into single hours.
    """
    total, nq = 0, 0
    for a in range(t, t + DAY, 6 * 3600):
        c, q = count_piece(cli, sub, a, a + 6 * 3600)
        nq += q
        if c is None:
            for h in range(a, a + 6 * 3600, 3600):
                c1, q1 = count_piece(cli, sub, h, h + 3600)
                nq += q1
                if c1 is None:
                    raise RuntimeError(f"hour window still times out at {h}")
                total += c1
        else:
            total += c
    return total, nq


def month_matches(cli, sub, start, end, wd, max_wd=31):
    """Matches in [start, end) summed over windows of `wd` whole UTC days."""
    t, total, nq, days, tries, retried = start, 0, 0, 0, 0, False
    while t < end:
        b = min(end, t + wd * DAY)
        ts = time.monotonic()
        try:
            data = cli.get("/api/comments/search/aggregate", subreddit=sub, body=QUERY,
                           aggregate="created_utc", frequency="day", after=t, before=b)
        except Timeout:
            nq += 1
            if wd == 1:
                tries += 1
                if tries >= 2:  # a heavy day (election week): count it in hour-aligned pieces
                    c, q = day_by_hours(cli, sub, t)
                    nq += q; total += c; days += 1
                    t, tries, retried = t + DAY, 0, False
                    continue
                time.sleep(10)
            else:
                wd = max(1, wd // 2)
                time.sleep(3)
            continue
        nq += 1
        c = sum(int(x["count"]) for x in data)
        if c == 0 and days and total / days > 2 and not retried:
            retried = True  # a zero amid a busy month: ask once more before believing it
            time.sleep(5)
            continue
        total += c
        days += (b - t) // DAY
        t, tries, retried = b, 0, False
        if time.monotonic() - ts < 2.5:
            wd = min(wd * 2, max_wd)
    return total, nq, wd


def strided(months):
    order, seen = [], set()
    for step in (12, 6, 3, 1):
        for i in range(0, len(months), step):
            if i not in seen:
                seen.add(i); order.append(months[i])
    return order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subs", nargs="*", default=["pics", "mildlyinteresting"])
    ap.add_argument("--interval", type=float, default=2.5)
    ap.add_argument("--verify", type=int, default=0,
                    help="recount this many stored months day by day and compare")
    args = ap.parse_args()
    out_dir = pathlib.Path("data/out/comment_index")
    out_dir.mkdir(parents=True, exist_ok=True)
    cli = Client(args.interval)
    if args.verify:
        for s in args.subs:
            recs = [json.loads(l) for l in (out_dir / f"{s}.jsonl").read_text().splitlines() if l.strip()]
            recs.sort(key=lambda r: r["month"])
            for r in recs[:: max(1, len(recs) // args.verify)][: args.verify]:
                y, m = map(int, r["month"].split("-"))
                start = int(dt.datetime(y, m, 1, tzinfo=dt.timezone.utc).timestamp())
                n, nq, _ = month_matches(cli, s, start, start + calendar.monthrange(y, m)[1] * DAY, 1, max_wd=1)
                ok = "ok" if n == r["matches"] else "MISMATCH"
                print(f"verify r/{s} {r['month']}: stored {r['matches']:,} vs daily {n:,} -> {ok}", flush=True)
        return
    totals = {s: monthly_totals(s) for s in args.subs}
    done = {s: set() for s in args.subs}
    for s in args.subs:
        f = out_dir / f"{s}.jsonl"
        if f.exists():
            done[s] = {json.loads(l)["month"] for l in f.read_text().splitlines() if l.strip()}
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    months = sorted({k for s in args.subs for k, v in totals[s].items() if v > 0 and k < now})
    width = {s: 7 for s in args.subs}  # days
    t0 = time.time()
    for k in strided(months):
        y, m = map(int, k.split("-"))
        start = int(dt.datetime(y, m, 1, tzinfo=dt.timezone.utc).timestamp())
        end = start + calendar.monthrange(y, m)[1] * DAY
        for s in args.subs:
            if k in done[s] or not totals[s].get(k):
                continue
            try:
                n, nq, width[s] = month_matches(cli, s, start, end, width[s])
            except RuntimeError as e:
                print(f"  !! r/{s} {k}: {e}", flush=True)
                continue
            rec = {"month": k, "matches": n, "total": totals[s][k],
                   "rate": round(n / totals[s][k], 5), "queries": nq}
            with open(out_dir / f"{s}.jsonl", "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(f"r/{s} {k}: {n:>7,} / {totals[s][k]:>9,} = {rec['rate']:.2%} "
                  f"({nq} q) [{(time.time() - t0) / 60:.0f} min]", flush=True)
    print("comment_index done", flush=True)


if __name__ == "__main__":
    main()
