import pathlib, time, json
from honest_sub.arctic import ArcticShift
from honest_sub.harvest import harvest_subreddit

api = ArcticShift(min_interval=0.4)
out = pathlib.Path("data/raw")
for sub in ["conspiracy", "science", "TrueUnpopularOpinion"]:
    t0 = time.time()
    s = harvest_subreddit(api, sub, out, years_back=2, quota_per_window=120, per_year=2)
    s["seconds"] = round(time.time() - t0, 1)
    print(json.dumps({k: s[k] for k in ["subreddit","posts","windows","bytes","seconds"]}))
