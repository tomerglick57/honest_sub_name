"""Reduce crowd_coactivity.jsonl to per-bucket shares with Wilson CIs."""
import json, pathlib, sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.slant import wilson

rows = [json.loads(l) for l in open("data/out/crowd_coactivity.jsonl") if l.strip()]
by = defaultdict(lambda: [0, 0])
for r in rows:
    k = (r["sub"], r["bucket"])
    by[k][1] += 1
    by[k][0] += bool(r["political"])
out = defaultdict(dict)
for (sub, b), (k, n) in sorted(by.items()):
    lo, hi = wilson(k, n)
    out[sub][b] = {"share": round(k / n, 4), "n": n,
                   "ci": [round(lo, 4), round(hi, 4)]}
pathlib.Path("data/out/crowd_series.json").write_text(json.dumps(out, indent=1))
for sub in out:
    print(f"r/{sub}:")
    for b, v in out[sub].items():
        print(f"  {b}: {v['share']:6.1%}  (n={v['n']})")
