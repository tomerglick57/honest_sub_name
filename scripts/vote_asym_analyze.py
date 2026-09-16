"""M1 for r/pics: vote asymmetry between sides among surviving submissions.

Each labeled survivor's score becomes a percentile among ALL survivors of
its month (census), so traffic growth cancels. Advocacy-left vs
advocacy-right (quotation posts dropped) are compared with Mann-Whitney U:
rank-biserial effect, normal-approximation p, permutation p (5,000 label
shuffles), top-decile counts, and achieved power for rank-biserial 0.2.
Also reports political-vs-not as the lift the front-page series implies.
"""
import bisect, json, math, pathlib, random, sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.harvest import read_posts

SUB = sys.argv[1] if len(sys.argv) > 1 else "pics"
D = pathlib.Path("data/out/vote_asym")


def load(path, key):
    d = {}
    for ln in path.read_text().splitlines() if path.exists() else []:
        try:
            r = json.loads(ln); d[r["id"]] = (r["month"], r[key])
        except (json.JSONDecodeError, KeyError):
            pass
    return d


def mw(a, b):
    """Rank-biserial (positive = a ranks higher), two-sided normal p with tie correction."""
    allv = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    n1, n2 = len(a), len(b); N = n1 + n2
    ranks, i, tie = {}, 0, 0.0
    rsum = 0.0
    while i < N:
        j = i
        while j < N and allv[j][0] == allv[i][0]:
            j += 1
        r = (i + j + 1) / 2
        t = j - i; tie += t ** 3 - t
        rsum += r * sum(1 for k in range(i, j) if allv[k][1] == 0)
        i = j
    u = rsum - n1 * (n1 + 1) / 2
    rb = 2 * u / (n1 * n2) - 1
    sd = math.sqrt(n1 * n2 / 12 * ((N + 1) - tie / (N * (N - 1)))) if N > 1 else 0
    z = (u - n1 * n2 / 2) / sd if sd else 0
    p = math.erfc(abs(z) / math.sqrt(2))
    return rb, p


def power(n1, n2, rb=0.2):
    sd = math.sqrt((n1 + n2 + 1) / (3 * n1 * n2))
    return 0.5 * math.erfc(-(rb / sd - 1.96) / math.sqrt(2))


def main():
    lab, quo = load(D / f"{SUB}.labels.jsonl", "label"), load(D / f"{SUB}.quotes.jsonl", "q")
    months = sorted({m for m, _ in lab.values()})
    pct = {}
    for f in sorted((pathlib.Path("data/census") / SUB).glob("*.jsonl.zst")):
        m = f.name[:7]
        if m not in months:
            continue
        surv = [p for p in read_posts(f) if not p.get("removed_by_category")]
        scores = sorted(p.get("score") or 0 for p in surv)
        for p in surv:
            if p["id"] in lab:
                s = p.get("score") or 0
                lo, hi = bisect.bisect_left(scores, s), bisect.bisect_right(scores, s)
                pct[p["id"]] = ((lo + hi) / 2 / len(scores), s, p.get("upvote_ratio"))
    grp = defaultdict(list)
    for i, (m, l) in lab.items():
        if i not in pct:
            continue
        grp[l].append(pct[i])
        if l in ("L", "R"):
            q = quo.get(i, (None, "UNC"))[1]
            grp[f"{q}-{l}"].append(pct[i])
    out = {"months": [months[0], months[-1]], "n": {k: len(v) for k, v in grp.items()},
           "deciles": {k: [sum(1 for x in v if int(min(x[0], 0.9999) * 10) == d) for d in range(10)]
                       for k, v in grp.items() if k in ("O", "P", "ADV-L", "ADV-R")}}
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
    print(f"r/{SUB} survivors {months[0]}..{months[-1]}: " + ", ".join(f"{k} {len(v)}" for k, v in sorted(grp.items())))
    for name, ka, kb in (("political vs not", ["P", "L", "R"], ["O"]),
                         ("all sided: left vs right", ["L"], ["R"]),
                         ("ADVOCACY only: left vs right", ["ADV-L"], ["ADV-R"])):
        a = [x[0] for k in ka for x in grp[k]]; b = [x[0] for k in kb for x in grp[k]]
        if len(a) < 5 or len(b) < 5:
            continue
        rb, p = mw(a, b)
        rng, hits = random.Random(0), 0
        pool = a + b
        for _ in range(5000):
            rng.shuffle(pool)
            if abs(mw(pool[:len(a)], pool[len(a):])[0]) >= abs(rb):
                hits += 1
        pp = (hits + 1) / 5001
        top = (sum(x >= 0.9 for x in a), sum(x >= 0.9 for x in b))
        ur = (med([x[2] for k in ka for x in grp[k] if x[2] is not None and x[1] >= 10]),
              med([x[2] for k in kb for x in grp[k] if x[2] is not None and x[1] >= 10]))
        res = {"n": [len(a), len(b)], "median_pct": [round(med(a), 3), round(med(b), 3)],
               "rank_biserial": round(rb, 3), "p": p, "perm_p": pp, "top_decile": top,
               "upvote_ratio_med": ur, "power_rb0.2": round(power(len(a), len(b)), 2)}
        out[name] = res
        print(f"\n{name}: n={len(a)} vs {len(b)}  median pctile {med(a):.2f} vs {med(b):.2f}  "
              f"rank-biserial {rb:+.3f}  p={p:.2g}  perm p={pp:.2g}  top decile {top[0]}:{top[1]}  "
              f"upvote ratio {ur[0]} vs {ur[1]}  power(rb=0.2)={power(len(a), len(b)):.0%}")
    (D / f"{SUB}.result.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
