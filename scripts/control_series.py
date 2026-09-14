"""Monthly front-page political share for a control sub, same method as r/pics.

Reads the control's census and labels (scripts/census.py --since, then
frontpage_label.py) and writes data/out/control_frontpage.json for the
monitor page. A month counts once >=80% of its front-page posts are labeled.
"""
import datetime as dt, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.frontpage import top_of_days
from honest_sub.harvest import read_posts

SUB = sys.argv[1] if len(sys.argv) > 1 else "mildlyinteresting"
CDIR = pathlib.Path("data/census") / SUB
LABELS = pathlib.Path("data/out/frontpage") / f"{SUB}.labels.jsonl"
OUT = pathlib.Path("data/out/control_frontpage.json")
MATURE = 3 * 86400
UTC = dt.timezone.utc

lab = {}
for ln in LABELS.read_text().splitlines() if LABELS.exists() else []:
    try:
        r = json.loads(ln); lab[r["id"]] = r["label"]
    except (json.JSONDecodeError, KeyError):
        pass
months = []
for f in sorted(CDIR.glob("*.jsonl.zst")):
    cutoff = f.stat().st_mtime - MATURE
    posts, n, pol, L, R = 0, 0, 0, 0, 0
    for d, ps in top_of_days(read_posts(f), 10).items():
        if dt.datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() + 86400 > cutoff:
            continue
        for p in ps:
            posts += 1
            l = lab.get(p["id"])
            if l is None:
                continue
            n += 1; pol += l != "O"; L += l == "L"; R += l == "R"
    months.append({"month": f.name[:7], "fp_posts": posts, "fp_n": n, "fp_pol": pol, "fp_L": L, "fp_R": R,
                   "fp_share": round(pol / n, 4) if posts and n >= 0.8 * posts else None})
OUT.write_text(json.dumps({"sub": SUB, "generated": dt.datetime.now(UTC).isoformat(timespec="minutes"),
                           "months": months}))
for m in months:
    if m["fp_share"] is not None:
        print(f"{m['month']} r/{SUB} front page political {m['fp_share']:5.1%} (n={m['fp_n']}) L{m['fp_L']} R{m['fp_R']}")
