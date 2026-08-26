"""Compute the measured honesty gap for every harvested subreddit."""
import json, pathlib, sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.signals import profile, log_odds_prior
from honest_sub.corpus import completed, path_for, targets_meta
from honest_sub.llm import discover
from honest_sub.gap import embed, cosine, score_cohort, MIN_REMOVED_TOKENS

OUT = pathlib.Path("data/meta/gap_scores.json")


def main():
    base = discover()
    subs = completed()
    meta = targets_meta()
    print(f"profiling {len(subs)} subs…", flush=True)
    profs = {s: profile(path_for(s)) for s in subs}
    bg = Counter()
    for p in profs.values():
        bg.update(p["kept_words"])

    records = []
    for s in subs:
        p, m = profs[s], meta.get(s, {})
        rw = p["removed_words"]
        removed_terms, match = [], None
        if sum(rw.values()) >= MIN_REMOVED_TOKENS:
            removed_terms = [w for w, _, _ in log_odds_prior(rw, p["kept_words"], top=18)]
            identity = f"{s}. {(m.get('public_description') or '')[:300]}"
            e = embed(base, [identity, ", ".join(removed_terms)])
            match = round(cosine(e[0], e[1]), 4)
        records.append({
            "subreddit": s,
            "subscribers": m.get("subscribers"),
            "mod_removal_rate": p["mod_removal_rate"],
            "identity_match": match,
            "removed_terms": removed_terms,
            "top20_author_share": p["top20_author_share"],
        })

    score_cohort(records)
    records.sort(key=lambda r: -r["gap_score"])
    OUT.write_text(json.dumps(records, indent=1))
    print(f"\n{'sub':26}{'score':>7}{'sev':>10}{'mod-rm':>8}{'ident':>7}")
    for r in records[:22]:
        print(f"r/{r['subreddit']:24}{r['gap_score']:>7.2f}{r['gap_severity']:>10}"
              f"{r['mod_removal_rate']:>8.0%}{(r['identity_match'] or 0):>7.2f}")
    from collections import Counter as C
    print("\nseverity:", dict(C(r["gap_severity"] for r in records)))


if __name__ == "__main__":
    main()
