"""Assemble the r/pics monitor series from the census, labels and comment index.

Every rate here is computed within its own day, week or month, so Reddit's
traffic growth and score inflation cancel by construction. Works on partial
data: months not yet censused are absent, and a week counts as scanned only
when >=80% of its front-page posts carry a label.

Output: data/out/pics_monitor.json (consumed by scripts/pics_monitor.py).
"""
import datetime as dt, json, pathlib, sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.frontpage import month_sample, top_of_days
from honest_sub.harvest import read_posts
from honest_sub.keywords import POL

SUB, N, K = "pics", 10, 100
CDIR = pathlib.Path("data/census") / SUB
LABELS = pathlib.Path("data/out/frontpage") / f"{SUB}.labels.jsonl"
CIDX = pathlib.Path("data/out/comment_index")
OUT = pathlib.Path("data/out/pics_monitor.json")
BASE_SUB = "mildlyinteresting"
MATURE = 3 * 86400    # a day's scores are final once it is 3 days old at harvest
BASE_END = "2015-12"  # "normal range" = the pre-2016 photo era; Jan/Jul 2017-2023 already sat above it
MOD = ("moderator", "automod_filtered")
UTC = dt.timezone.utc
ANON = ("[deleted]", "AutoModerator")
YEAR = 365 * 86400
C24 = int(dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc).timestamp())


def tenure(p, first):
    """'new' = the poster's first r/pics post (census back to 2008) was under a
    year earlier, this post included; 'reg' = a year or more; None = no author."""
    a = p.get("author")
    if not a or a in ANON or a not in first:
        return None
    return "new" if p["created_utc"] - first[a] < YEAR else "reg"


VALIDATE = pathlib.Path("data/out/frontpage") / f"{SUB}.validate.jsonl"


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def reasoning_check():
    """Agreement of the fast labels with the same model re-run WITH reasoning
    (scripts/frontpage_validate.py: stratified by era x label)."""
    if not VALIDATE.exists():
        return None
    rows = [json.loads(l) for l in VALIDATE.read_text().splitlines() if l.strip()]
    if not rows:
        return None
    pol = lambda l: l != "O"
    b = [(pol(r["fast"]), pol(r["slow"])) for r in rows]
    recent = [(pol(r["fast"]), pol(r["slow"])) for r in rows if r["month"] >= "2024"]
    f4 = [(r["fast"], r["slow"]) for r in rows]
    agree = lambda ps: round(sum(a == c for a, c in ps) / len(ps), 3) if ps else None
    return {"n": len(rows), "binary": agree(b), "binary_kappa": round(kappa(b), 2),
            "binary_recent": agree(recent), "four": agree(f4), "four_kappa": round(kappa(f4), 2),
            "r_to_l": sum(a == "R" and c == "L" for a, c in f4),
            "l_to_r": sum(a == "L" and c == "R" for a, c in f4)}


SUBJECTS = pathlib.Path("data/out/frontpage") / f"{SUB}.subjects.jsonl"
SUBJ_KEYS = ("T", "I", "E", "P", "F", "S", "O")  # H (history) folds into O


def load_subjects():
    out = {}
    for ln in SUBJECTS.read_text().splitlines() if SUBJECTS.exists() else []:
        try:
            r = json.loads(ln)
            out[r["id"]] = "O" if r["subject"] == "H" else r["subject"]
        except (json.JSONDecodeError, KeyError):
            pass
    return out


def load_labels():
    lab = {}
    for ln in LABELS.read_text().splitlines() if LABELS.exists() else []:
        try:
            r = json.loads(ln)
            lab[r["id"]] = r["label"]
        except (json.JSONDecodeError, KeyError):
            pass
    return lab


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    i = (len(xs) - 1) * q
    lo = int(i)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def comment_rates(sub):
    f = CIDX / f"{sub}.jsonl"
    out = {}
    for ln in f.read_text().splitlines() if f.exists() else []:
        r = json.loads(ln)
        out[r["month"]] = r
    return out


def main():
    lab = load_labels()
    subj = load_subjects()
    counts = json.loads((CDIR / "_counts.json").read_text())
    now_m = dt.datetime.now(UTC).strftime("%Y-%m")
    all_months = [k for k in sorted(counts) if counts[k] > 0 and k <= now_m]
    weeks = defaultdict(lambda: {"posts": 0, "n": 0, "pol": 0, "L": 0, "R": 0, "titles": []})
    months, kw = {}, Counter()
    files = sorted(CDIR.glob("*.jsonl.zst"))
    first = {}  # author -> their first r/pics post, over the whole census
    for f in files:
        for p in read_posts(f):
            a = p.get("author")
            if a and a not in ANON and (a not in first or p["created_utc"] < first[a]):
                first[a] = p["created_utc"]
    for f in files:
        k = f.name[:7]
        cutoff = f.stat().st_mtime - MATURE
        posts = list(read_posts(f))
        m = months[k] = dict(month=k, posts=len(posts), expected=counts.get(k),
                             fp_posts=0, fp_n=0, fp_pol=0, fp_L=0, fp_R=0, fp_P=0,
                             fp_rm_pol=0, fp_rm_non=0, fp_flair=0, fp_flair_pol=0,
                             fp_new_n=0, fp_new_pol=0, fp_reg_n=0, fp_reg_pol=0,
                             fp_c24_n=0, fp_c24_pol=0,
                             sub_n=0, sub_pol=0, sub_vis_n=0, sub_vis_pol=0,
                             sub_rm_n=0, sub_rm_pol=0,
                             sub_new_n=0, sub_new_pol=0, sub_reg_n=0, sub_reg_pol=0,
                             subj={k: 0 for k in SUBJ_KEYS}, subj_n=0)
        for d, ps in top_of_days(posts, N).items():
            if dt.datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() + 86400 > cutoff:
                continue  # scores still accruing when harvested
            W = weeks[(d.year, min(51, (d - dt.date(d.year, 1, 1)).days // 7))]
            for p in ps:
                m["fp_posts"] += 1; W["posts"] += 1
                l = lab.get(p["id"])
                if l is None:
                    continue
                pol = l != "O"
                m["fp_n"] += 1; W["n"] += 1
                rm = p.get("removed_by_category") in MOD
                if pol:
                    m["fp_pol"] += 1; m[f"fp_{l}"] += 1; W["pol"] += 1
                    if l in "LR":
                        W[l] += 1
                    W["titles"].append((p.get("score") or 0, p.get("title") or "", l))
                    m["fp_rm_pol"] += rm
                    if p["id"] in subj:
                        m["subj"][subj[p["id"]]] += 1; m["subj_n"] += 1
                else:
                    m["fp_rm_non"] += rm
                if "politic" in (p.get("link_flair_text") or "").lower():
                    m["fp_flair"] += 1; m["fp_flair_pol"] += pol
                t = tenure(p, first)
                if t:
                    m[f"fp_{t}_n"] += 1; m[f"fp_{t}_pol"] += pol
                if first.get(p.get("author"), 0) >= C24:
                    m["fp_c24_n"] += 1; m["fp_c24_pol"] += pol
                era = "2008-15" if k < "2016" else "2016-23" if k < "2024" else "2024-26"
                kw[(era, pol, bool(POL.search(p.get("title") or "")))] += 1
        for p in month_sample(posts, SUB, k, K):
            l = lab.get(p["id"])
            if l is None:
                continue
            pol, rbc = l != "O", p.get("removed_by_category")
            m["sub_n"] += 1; m["sub_pol"] += pol
            t = tenure(p, first)
            if t:
                m[f"sub_{t}_n"] += 1; m[f"sub_{t}_pol"] += pol
            if rbc != "reddit":  # site spam filter: never visible to anyone
                m["sub_vis_n"] += 1; m["sub_vis_pol"] += pol
            if rbc in MOD:
                m["sub_rm_n"] += 1; m["sub_rm_pol"] += pol
        m["rm_mod"] = sum(p.get("removed_by_category") in MOD for p in posts)
        m["rm_reddit"] = sum(p.get("removed_by_category") == "reddit" for p in posts)
        m["rm_deleted"] = sum(p.get("removed_by_category") == "deleted" for p in posts)
        m["locked"] = sum(bool(p.get("locked")) for p in posts)
        m["tracked"] = any(p.get("removed_by_category") for p in posts)

    cp, cb = comment_rates(SUB), comment_rates(BASE_SUB)
    for k, m in months.items():
        m["c_pics"] = cp.get(k, {}).get("rate")
        m["c_base"] = cb.get(k, {}).get("rate")
    scanned = lambda m: m["fp_posts"] and m["fp_n"] >= 0.8 * m["fp_posts"]
    rows = []
    for k in all_months:
        m = months.get(k)
        if not m:
            rows.append({"month": k, "censused": False,
                         "c_pics": cp.get(k, {}).get("rate"), "c_base": cb.get(k, {}).get("rate")})
            continue
        rows.append(dict(m, censused=True,
                         fp_share=round(m["fp_pol"] / m["fp_n"], 4) if scanned(m) else None,
                         sub_share=round(m["sub_pol"] / m["sub_n"], 4) if m["sub_n"] >= 60 else None,
                         sub_vis_share=round(m["sub_vis_pol"] / m["sub_vis_n"], 4) if m["sub_vis_n"] >= 40 else None))

    base = [r["fp_share"] for r in rows if r.get("fp_share") is not None and r["month"] <= BASE_END]
    band = {"p10": quantile(base, .1), "p50": quantile(base, .5), "p90": quantile(base, .9), "n": len(base)}
    wk = []
    for (y, w), W in sorted(weeks.items()):
        ok = W["posts"] and W["n"] >= 0.8 * W["posts"]
        W["titles"].sort(key=lambda t: -t[0])
        wk.append({"y": y, "w": w, "posts": W["posts"], "n": W["n"], "pol": W["pol"],
                   "L": W["L"], "R": W["R"],
                   "share": round(W["pol"] / W["n"], 4) if ok else None,
                   "titles": [{"s": s, "t": t[:200], "l": l} for s, t, l in W["titles"][:3]]})

    flair = [r for r in rows if r.get("fp_flair")]
    val = {"flair_recall": (sum(r["fp_flair_pol"] for r in flair), sum(r["fp_flair"] for r in flair)),
           "keyword_vs_llm": {f"{e}|llm_pol={int(p)}|kw={int(q)}": v for (e, p, q), v in sorted(kw.items())},
           "labels": len(lab), "subjects": len(subj), "reasoning": reasoning_check()}
    census = {"months_done": len(months), "months_total": len(all_months),
              "posts": sum(m["posts"] for m in months.values()),
              "expected": sum(counts[k] for k in months),
              "worst_ratio": min((m["posts"] / m["expected"], k) for k, m in months.items() if m["expected"])
              if months else None}
    OUT.write_text(json.dumps({"generated": dt.datetime.now(UTC).isoformat(timespec="minutes"),
                               "census": census, "band": band, "months": rows, "weeks": wk,
                               "validation": val}, ensure_ascii=False))
    print(f"census {census['months_done']}/{census['months_total']} months, "
          f"{census['posts']:,} posts; {len(lab):,} labels; worst month ratio {census['worst_ratio']}")
    print(f"normal band (months <= {BASE_END}, n={band['n']}): {band}")
    print(f"flair recall: {val['flair_recall']}")
    for r in rows:
        if r.get("fp_share") is not None:
            print(f"  {r['month']} fp {r['fp_share']:6.1%} (n={r['fp_n']}) L{r['fp_L']} R{r['fp_R']}"
                  f" | sub {r['sub_share'] if r['sub_share'] is None else format(r['sub_share'], '.1%')}"
                  f" | rm_mod {r['rm_mod'] / r['posts']:.1%} | c {r['c_pics']} / {r['c_base']}")


if __name__ == "__main__":
    main()
