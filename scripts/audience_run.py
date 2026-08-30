"""Phase 1 audience metrics: vote asymmetry (M1) and visibility mix (M2).

Reuses the stance labels banked by slant_run.py -- zero new classification.
Survivors only, per the survivorship rule in docs/audience-methodology.md:
removed posts stop accruing votes, so including them would re-discover the
moderation effect and mislabel it an audience effect.
"""
import json, pathlib, random, sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.harvest import read_posts
from scipy.stats import mannwhitneyu

OUT = pathlib.Path("data/out/audience.json")
LABELS = pathlib.Path("data/out/slant_labels")
MANIFESTS = pathlib.Path("data/out/slant_manifests")
SUBS = ["conspiracy", "Conservative", "politics"]


def corpus_path(sub):
    deep = pathlib.Path(f"data/raw_deep/{sub}.posts.jsonl.zst")
    return deep if deep.exists() else pathlib.Path(f"data/raw/{sub}.posts.jsonl.zst")


def load_labels(sub):
    """id -> label, recovering legacy title-keyed rows via the manifest."""
    man = json.loads((MANIFESTS / f"{sub}.json").read_text())
    by_title = {m["title"]: m["id"] for m in man}
    out = {}
    for ln in (LABELS / f"{sub}.jsonl").read_text().splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        pid = r.get("id") or by_title.get(r.get("title", ""))
        if pid:
            out[pid] = r["label"]
    return out


def month_percentiles(survivors):
    """post id -> percentile of score within its (year, month) cohort.

    Cohorts are ALL surviving posts in the corpus, not just labelled ones, so a
    percentile means standing against everything the sub's readers saw that
    month. Sub-month normalisation absorbs traffic growth over the years.
    """
    import datetime as dt
    cohort = defaultdict(list)
    for p in survivors:
        d = dt.datetime.fromtimestamp(p["created_utc"], dt.timezone.utc)
        cohort[(d.year, d.month)].append(p)
    pct = {}
    for _, posts in cohort.items():
        posts.sort(key=lambda p: (p.get("score") or 0))
        n = len(posts)
        i = 0
        while i < n:  # ties share the mean rank
            j = i
            while j + 1 < n and (posts[j + 1].get("score") or 0) == (posts[i].get("score") or 0):
                j += 1
            for k in range(i, j + 1):
                pct[posts[k]["id"]] = ((i + j) / 2) / max(1, n - 1)
            i = j + 1
    return pct


def rank_biserial(a, b):
    u = mannwhitneyu(a, b, alternative="two-sided").statistic
    return 2 * u / (len(a) * len(b)) - 1


def permutation_p(a, b, n_iter=5000, seed=0):
    obs = abs(rank_biserial(a, b))
    pool = a + b
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_iter):
        rng.shuffle(pool)
        if abs(rank_biserial(pool[:len(a)], pool[len(a):])) >= obs:
            hits += 1
    return (hits + 1) / (n_iter + 1)


def main():
    results = []
    for sub in SUBS:
        posts = {p["id"]: p for p in read_posts(corpus_path(sub))}
        survivors = [p for p in posts.values() if not p.get("removed_by_category")]
        pct = month_percentiles(survivors)
        labels = load_labels(sub)

        import math
        sided = {"A": [], "B": []}
        weight = {"A": 0.0, "B": 0.0}
        topdec = {"A": 0, "B": 0}
        for pid, lab in labels.items():
            if lab not in ("A", "B") or pid not in pct:
                continue  # removed, or not a survivor in corpus
            sided[lab].append(pct[pid])
            weight[lab] += math.log10(1 + max(0, posts[pid].get("score") or 0))
            if pct[pid] >= 0.9:
                topdec[lab] += 1

        A, B = sided["A"], sided["B"]
        if len(A) < 20 or len(B) < 20:
            results.append({"subreddit": sub, "skipped": f"n_A={len(A)} n_B={len(B)}"})
            continue
        mw = mannwhitneyu(A, B, alternative="two-sided")
        wtot = weight["A"] + weight["B"]
        r = {
            "subreddit": sub,
            "n_A_surviving": len(A), "n_B_surviving": len(B),
            "median_pctile_A": round(sorted(A)[len(A) // 2], 3),
            "median_pctile_B": round(sorted(B)[len(B) // 2], 3),
            "rank_biserial": round(rank_biserial(A, B), 4),  # >0: A ranks higher
            "mw_p": float(f"{mw.pvalue:.4g}"),
            "perm_p": permutation_p(A, B),
            "raw_mix_A_share": round(len(A) / (len(A) + len(B)), 3),
            "visibility_mix_A_share": round(weight["A"] / wtot, 3) if wtot else None,
            "top_decile_A_B": [topdec["A"], topdec["B"]],
        }
        results.append(r)
        print(json.dumps(r, indent=1), flush=True)
    OUT.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
