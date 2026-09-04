"""Batch-2 analysis: pooled G1 verdict, M4 self-deletion asymmetry, M3 attrition."""
import json, pathlib, random, sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.harvest import read_posts
from honest_sub.slant import fisher_exact_two_sided, wilson
from scipy.stats import mannwhitneyu, fisher_exact

L = pathlib.Path("data/out")


def jl(p):
    """Tolerates a missing file: a deadline can cut a stage short, and the
    analysis must report what exists rather than crash on what does not --
    the first run of this script lost an already-computed G1 PASS that way."""
    p = pathlib.Path(p)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def month_pct(posts):
    import datetime as dt
    cohort = defaultdict(list)
    for p in posts:
        if not p.get("removed_by_category"):
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
    return 2 * mannwhitneyu(a, b, alternative="two-sided").statistic / (len(a)*len(b)) - 1


def perm_rb(a, b, n=5000, seed=0):
    obs = abs(rb(a, b)); pool = a + b; rng = random.Random(seed); h = 0
    for _ in range(n):
        rng.shuffle(pool)
        if abs(rb(pool[:len(a)], pool[len(a):])) >= obs:
            h += 1
    return (h + 1) / (n + 1)


lines = []
def say(s=""):
    print(s, flush=True); lines.append(s)


# ---------- G1 pooled ----------
sub = "Conservative"
posts = {p["id"]: p for p in read_posts(pathlib.Path("data/raw_deep/Conservative.posts.jsonl.zst"))}
pct = month_pct(posts.values())
man = json.loads((L/"slant_manifests/Conservative.json").read_text())
by_title = {m["title"]: m["id"] for m in man}
st = {}
for r in jl(L/"slant_labels/Conservative.jsonl"):
    pid = r.get("id") or by_title.get(r.get("title", ""))
    if pid: st[pid] = r["label"]
for r in jl(L/"slant_labels/Conservative.survivors.jsonl"):
    st[r["id"]] = r["label"]
q = {r["id"]: r["q"] for r in jl(L/"q_labels/Conservative.jsonl")}
q.update({r["id"]: r["q"] for r in jl(L/"q_labels/Conservative.survivors.jsonl")})
va = [pct[p] for p, l in st.items() if l == "A" and q.get(p) == "ADV" and p in pct]
vb = [pct[p] for p, l in st.items() if l == "B" and q.get(p) == "ADV" and p in pct]
mw = mannwhitneyu(va, vb, alternative="two-sided")
e = rb(va, vb)
say("=== G1 pooled (r/Conservative, advocacy-only survivors) ===")
say(f"n_A={len(va)} n_B={len(vb)}  median A={sorted(va)[len(va)//2]:.3f} B={sorted(vb)[len(vb)//2]:.3f}")
say(f"rank_biserial={e:.4f} (expected <0)  MW p={mw.pvalue:.4g}  perm p={perm_rb(va, vb):.4g}")
verdict = "PASSES" if (e < 0 and mw.pvalue < 0.05) else ("direction OK, underpowered" if e < 0 else "FAILS")
say(f"G1: {verdict}")

# ---------- M4 ----------
say("\n=== M4 self-deletion asymmetry (deleted vs kept stance mix) ===")
for s in ("Conservative", "conspiracy", "politics"):
    manp = json.loads((L/f"slant_manifests/{s}.json").read_text())
    bt = {m["title"]: m["id"] for m in manp}
    rem = {m["id"]: m["removed"] for m in manp}
    stl = {}
    for r in jl(L/f"slant_labels/{s}.jsonl"):
        pid = r.get("id") or bt.get(r.get("title", ""))
        if pid: stl[pid] = r["label"]
    kept = [stl[p] for p in stl if stl[p] in ("A", "B") and rem.get(p) is False]
    dele = [r["label"] for r in jl(L/f"slant_labels/{s}.deleted.jsonl") if r["label"] in ("A", "B")]
    if len(dele) < 15:
        say(f"r/{s:14} insufficient deleted sided n={len(dele)}"); continue
    a_d, b_d = dele.count("A"), dele.count("B")
    a_k, b_k = kept.count("A"), kept.count("B")
    orr, p = fisher_exact([[a_d, b_d], [a_k, b_k]])
    say(f"r/{s:14} deleted A:B={a_d}:{b_d} ({a_d/(a_d+b_d):.0%} left)  kept A:B={a_k}:{b_k} "
        f"({a_k/(a_k+b_k):.0%} left)  OR={orr:.2f}  p={p:.3g}")

# ---------- M3 ----------
say("\n=== M3 attrition (advocacy authors returning to the sub within 90d) ===")
rows = jl(L/"m3_attrition.jsonl") if (L/"m3_attrition.jsonl").exists() else []
bysub = defaultdict(list)
for r in rows:
    if r["site_active"] or r["returned"]:
        bysub[r["sub"]].append(r)
for s, rs in bysub.items():
    pcts = None
    say(f"r/{s} (n={len(rs)} site-active advocacy pairs)")
    for stratum, f in (("removed", lambda r: r["removed"]),
                       ("kept", lambda r: not r["removed"])):
        aa = [r for r in rs if r["label"] == "A" and f(r)]
        bb = [r for r in rs if r["label"] == "B" and f(r)]
        if len(aa) < 15 or len(bb) < 15:
            say(f"  {stratum:8} insufficient (A={len(aa)} B={len(bb)})"); continue
        ra = sum(r["returned"] for r in aa) / len(aa)
        rbb = sum(r["returned"] for r in bb) / len(bb)
        p = fisher_exact_two_sided(sum(r["returned"] for r in aa), len(aa)-sum(r["returned"] for r in aa),
                                   sum(r["returned"] for r in bb), len(bb)-sum(r["returned"] for r in bb))
        say(f"  {stratum:8} return: A {ra:.0%} (n={len(aa)}) vs B {rbb:.0%} (n={len(bb)})  p={p:.3g}")

pathlib.Path("data/out/batch2_report.txt").write_text("\n".join(lines))

# ---------- M3 with visitor control (appended) ----------
prior_p = L / "m3_prior.jsonl"
if prior_p.exists():
    say("\n=== M3 stratified by prior in-sub activity (visitor control) ===")
    prior = {(r["sub"], r["id"]): r["prior_active"] for r in jl(prior_p)}
    for s, rs in bysub.items():
        regs = [r for r in rs if prior.get((r["sub"], r["id"])) is True]
        say(f"r/{s}: {len(regs)}/{len(rs)} pairs are prior-active regulars")
        for stratum, f in (("removed", lambda r: r["removed"]),
                           ("kept", lambda r: not r["removed"])):
            aa = [r for r in regs if r["label"] == "A" and f(r)]
            bb = [r for r in regs if r["label"] == "B" and f(r)]
            if len(aa) < 15 or len(bb) < 15:
                say(f"  regulars/{stratum:8} insufficient (A={len(aa)} B={len(bb)})"); continue
            ra = sum(r["returned"] for r in aa) / len(aa)
            rbb = sum(r["returned"] for r in bb) / len(bb)
            p = fisher_exact_two_sided(
                sum(r["returned"] for r in aa), len(aa) - sum(r["returned"] for r in aa),
                sum(r["returned"] for r in bb), len(bb) - sum(r["returned"] for r in bb))
            say(f"  regulars/{stratum:8} return: A {ra:.0%} (n={len(aa)}) vs B {rbb:.0%} (n={len(bb)})  p={p:.3g}")
        # visitor share by stance -- itself informative
        for lab in ("A", "B"):
            ls = [r for r in rs if r["label"] == lab]
            vs = sum(1 for r in ls if prior.get((r["sub"], r["id"])) is False)
            if ls:
                say(f"  visitor share among {lab}: {vs/len(ls):.0%} (n={len(ls)})")

pathlib.Path("data/out/batch2_report.txt").write_text("\n".join(lines))
