"""Advocacy-only redo of moderation and vote asymmetry, plus the G1 verdict.

Uses stance labels (A/B) intersected with q labels (ADV only). Non-advocacy
(QUO/UNC) is dropped, never flipped -- flipping would compound two error rates.
Also reports the quotation-genre map (QUO share by sub x stance x survival),
which is itself a finding about how each community talks about the other side.
"""
import json, pathlib, sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.harvest import read_posts
from honest_sub.slant import asymmetry, permutation_p
from scipy.stats import mannwhitneyu
import random

Q = pathlib.Path("data/out/q_labels")
MANIFESTS = pathlib.Path("data/out/slant_manifests")
SLANT = pathlib.Path("data/out/slant_labels")
SUBS = ["Conservative", "conspiracy", "politics", "PublicFreakout"]


def corpus(sub):
    p = pathlib.Path(f"data/raw_deep/{sub}.posts.jsonl.zst")
    return p if p.exists() else pathlib.Path(f"data/raw/{sub}.posts.jsonl.zst")


def load(sub):
    man = json.loads((MANIFESTS / f"{sub}.json").read_text())
    by_title = {m["title"]: m["id"] for m in man}
    removed = {m["id"]: m["removed"] for m in man}
    st = {}
    for ln in (SLANT / f"{sub}.jsonl").read_text().splitlines():
        if ln.strip():
            r = json.loads(ln)
            pid = r.get("id") or by_title.get(r.get("title", ""))
            if pid:
                st[pid] = r["label"]
    q = {}
    qf = Q / f"{sub}.jsonl"
    if qf.exists():
        for ln in qf.read_text().splitlines():
            if ln.strip():
                r = json.loads(ln)
                q[r["id"]] = r["q"]
    return st, q, removed


def month_pct(posts_by_id):
    import datetime as dt
    survivors = [p for p in posts_by_id.values() if not p.get("removed_by_category")]
    cohort = defaultdict(list)
    for p in survivors:
        d = dt.datetime.fromtimestamp(p["created_utc"], dt.timezone.utc)
        cohort[(d.year, d.month)].append(p)
    pct = {}
    for _, ps in cohort.items():
        ps.sort(key=lambda p: (p.get("score") or 0))
        n = len(ps)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and (ps[j+1].get("score") or 0) == (ps[i].get("score") or 0):
                j += 1
            for k in range(i, j + 1):
                pct[ps[k]["id"]] = ((i + j) / 2) / max(1, n - 1)
            i = j + 1
    return pct


def rb(a, b):
    return 2 * mannwhitneyu(a, b, alternative="two-sided").statistic / (len(a) * len(b)) - 1


def perm_rb(a, b, n_iter=5000, seed=0):
    obs = abs(rb(a, b)); pool = a + b; rng = random.Random(seed); hits = 0
    for _ in range(n_iter):
        rng.shuffle(pool)
        if abs(rb(pool[:len(a)], pool[len(a):])) >= obs:
            hits += 1
    return (hits + 1) / (n_iter + 1)


def main():
    results = []
    for sub in SUBS:
        st, q, man_removed = load(sub)
        posts = {p["id"]: p for p in read_posts(corpus(sub))}
        pct = month_pct(posts)

        # quotation-genre map over everything q-labelled
        genre = defaultdict(lambda: [0, 0])  # (stance, removed) -> [QUO, total]
        for pid, lab in st.items():
            if lab in ("A", "B") and pid in q:
                key = (lab, man_removed.get(pid))
                genre[key][1] += 1
                if q[pid] == "QUO":
                    genre[key][0] += 1
        genre_out = {f"{l}_{'removed' if r else 'kept'}":
                     {"quo_share": round(g[0]/g[1], 3), "n": g[1]}
                     for (l, r), g in genre.items() if g[1] and r is not None}

        # advocacy-only moderation asymmetry
        adv = [(pid, st[pid]) for pid in st
               if st[pid] in ("A", "B") and q.get(pid) == "ADV" and pid in man_removed]
        labels = [l for _, l in adv]
        flags = [man_removed[pid] for pid, _ in adv]
        mod = asymmetry(labels, flags)
        mod["perm_p"] = permutation_p(labels, flags)

        # advocacy-only vote asymmetry among survivors
        va = [pct[pid] for pid, l in adv if l == "A" and pid in pct]
        vb = [pct[pid] for pid, l in adv if l == "B" and pid in pct]
        vote = None
        if len(va) >= 15 and len(vb) >= 15:
            mw = mannwhitneyu(va, vb, alternative="two-sided")
            vote = {"n_A": len(va), "n_B": len(vb),
                    "median_A": round(sorted(va)[len(va)//2], 3),
                    "median_B": round(sorted(vb)[len(vb)//2], 3),
                    "rank_biserial": round(rb(va, vb), 4),
                    "mw_p": float(f"{mw.pvalue:.4g}"),
                    "perm_p": perm_rb(va, vb)}
        results.append({"subreddit": sub, "genre_map": genre_out,
                        "moderation_adv_only": {k: mod[k] for k in
                            ("n_A", "n_B", "rate_A", "rate_B", "odds_ratio",
                             "p_fisher", "perm_p")},
                        "vote_adv_only": vote or f"insufficient (A={len(va)} B={len(vb)})"})
        print(json.dumps(results[-1], indent=1), flush=True)

    pathlib.Path("data/out/audience2.json").write_text(json.dumps(results, indent=1))
    cons = next(r for r in results if r["subreddit"] == "Conservative")
    v = cons["vote_adv_only"]
    print("\n=== G1 verdict (advocacy-only, r/Conservative) ===")
    if isinstance(v, dict):
        direction_ok = v["rank_biserial"] < 0  # left advocacy should rank LOWER
        sig = v["mw_p"] < 0.05
        print(f"rank_biserial={v['rank_biserial']} (expected <0), p={v['mw_p']}, "
              f"n_A={v['n_A']} n_B={v['n_B']}")
        print("G1:", "PASSES" if (direction_ok and sig) else
              ("direction OK, underpowered" if direction_ok else "FAILS"))
    else:
        print("G1: cannot evaluate --", v)


if __name__ == "__main__":
    main()
