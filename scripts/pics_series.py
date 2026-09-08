"""r/pics political-share time series across every harvested corpus.

Merges the historical, shallow and deep harvests (dedup by post id). All
shares are computed WITHIN each half-year, so score inflation across Reddit
eras cancels by construction. The keyword screen carries a stated bias: its
vocabulary is denser for 2016+ politics (trump, maga, gaza...) than for
earlier eras, so early-era shares are more likely under- than overstated.
"""
import pathlib, re, datetime as dt, json, sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.harvest import read_posts

POL = re.compile(r"\b(trump|biden|harris|obama|romney|mccain|palin|clinton|hillary|sanders|"
    r"bush|cheney|pelosi|mcconnell|vance|musk|maga|tea party|occupy|president|congress|senate|"
    r"election|vote[rd]?s?|voting|ballot|democrat\w*|republican\w*|gop|liberal\w*|conservativ\w*|"
    r"protest\w*|rally|politic\w*|immigra\w*|deport\w*|\bice\b|border|abortion|obamacare|"
    r"gaza|israel\w*|palestin\w*|ukrain\w*|putin|zelensk\w*|epstein|luigi|mangione|iraq|afghanistan|"
    r"fascis\w*|nazi\w*|white house|supreme court|impeach\w*|tariff\w*|executive order|snowden|nsa)\b", re.I)

posts = {}
for f in ("data/raw_hist/pics.posts.jsonl.zst", "data/raw/pics.posts.jsonl.zst",
          "data/raw_deep/pics.posts.jsonl.zst"):
    p = pathlib.Path(f)
    if p.exists():
        for post in read_posts(p):
            posts[post["id"]] = post
print(f"merged corpus: {len(posts)} unique posts")

half = defaultdict(list)
for p in posts.values():
    d = dt.datetime.fromtimestamp(p["created_utc"], dt.timezone.utc)
    half[(d.year, 1 if d.month <= 6 else 2)].append(p)

series = []
pol = lambda p: bool(POL.search(p.get("title") or ""))
for (y, h) in sorted(half):
    ps = half[(y, h)]
    surv = [p for p in ps if not p.get("removed_by_category")]
    if len(surv) < 150:   # decile needs >=15 posts to mean anything
        continue
    top = sorted(surv, key=lambda p: -(p.get("score") or 0))[:max(1, len(surv)//10)]
    series.append(dict(label=f"{y} H{h}", n=len(surv),
                       raw=round(sum(map(pol, surv))/len(surv), 4),
                       top=round(sum(map(pol, top))/len(top), 4),
                       removal=round(sum(1 for p in ps if p.get("removed_by_category")=="moderator")/len(ps), 4)))
json.dump(series, open("data/out/pics_timeseries.json", "w"), indent=1)
for r in series:
    print(f"{r['label']}: n={r['n']:>5} raw={r['raw']:6.1%} top={r['top']:6.1%} rm={r['removal']:5.1%}")
