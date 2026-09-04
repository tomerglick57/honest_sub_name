"""Funnel-informed honest descriptions for the three deep-dive subs.

Every number on the sheet is measured; the model phrases. Same discipline as
the main pipeline: severity and asymmetries are never the model's opinion.
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.llm import LMStudio
from honest_sub.corpus import targets_meta

SYSTEM = """\
You write honest one-paragraph characterisations of subreddits from measured
evidence. You are given verified statistics about one subreddit: what gets
posted, what moderators remove, how voters rank content, and whether authors
return. Every claim you make must trace to a number on the sheet -- invent
nothing, soften nothing. Distinguish carefully between what the community
posts, what its moderators do, what its voters do, and who stays: these are
different actors and the sheet may show them pushing in different directions.
Write neutrally and specifically. Output JSON."""

SCHEMA = {
    "type": "object",
    "properties": {
        "honest_name": {"type": "string", "description": "short descriptive name, under 60 chars, not the sub's own name"},
        "honest_description": {"type": "string", "description": "3-5 sentences covering each gate the evidence describes"},
    },
    "required": ["honest_name", "honest_description"],
    "additionalProperties": False,
}

SHEETS = {
"conspiracy": """# r/conspiracy (2.19M subscribers; sidebar: general conspiracy discussion forum)
MEASURED FUNNEL (6,759 stance-classified posts; all p-values survive correction):
- Posted content: 47% not about US politics at all; 43% political-but-neutral; among sided posts, right-leaning outnumbers left 2.4:1 (467 vs 197).
- Moderators: remove right-leaning posts MORE than left (39.7% vs 27.6% advocacy-only, OR=0.58, p=0.0055). They do not enforce the right lean.
- Voters: neutral -- no ranking advantage to either side (rank-biserial -0.03, p=0.66).
- Retention: the one asymmetric gate. Left-advocacy authors whose posts SURVIVE return within 90 days at 69% vs 84% for right (p=0.0019). The lean is maintained by who keeps coming back, not by enforcement. (Caveat: visitor-vs-regular control pending.)
- Genre: argues in its own voice; quotation of public figures is rare (<=9%).""",
"Conservative": """# r/Conservative (1.20M subscribers; sidebar: forum for conservatives)
MEASURED FUNNEL (2,076 case-control + 4,600 survivor stance labels):
- Posted content: right-leaning outnumbers left 4.3:1 (557 vs 129 sided).
- Moderators: remove left-advocacy posts at 69.6% vs 46.0% for right (OR=2.68, p=7.6e-11).
- Voters: bury surviving left advocacy (rank-biserial -0.115, p=0.019).
- Self-deletion: left posters withdraw their own posts at 3.3x the odds (deleted posts are 30% left vs 11% of kept, p=3.3e-05) -- a pile-on signature.
- Retention: left-advocacy authors whose posts were removed return at 42% vs 68% for right (p=1.1e-08).
- Genre: 29% of surviving left-labelled posts are quotations of left figures showcased for the in-group; these dominate the top-scored "left" posts. Mock-quotation is the community's upvoted mode of engaging opponents.
- Note: the sub openly declares itself conservative; the finding is HOW the uniformity is produced -- by all four gates at once.""",
"politics": """# r/politics (8.4M subscribers; name implies general US politics forum; sidebar: news and discussion about US politics)
MEASURED FUNNEL (8,004 stance-classified posts):
- Posted content: left-leaning outnumbers right 3.6:1 (1371 vs 377 sided).
- Moderators: remove right-advocacy posts at 63.2% vs 40.6% for left (OR=0.40, p=2.7e-12). Source-quality rules were tested and do NOT explain this: removed posts are ~21% mainstream-sourced and kept ~38%, identically for both stances.
- Voters: bury surviving right content massively -- median percentile 0.13 vs 0.70 for left (rank-biserial 0.757, p=8.7e-38); of survivors reaching the top score decile, 142 are left vs 1 right.
- Combined visibility: after moderation and voting, the visible sub is ~96% left.
- Retention: right-advocacy authors whose posts were KEPT still return less (78% vs 91%, p=1.5e-4).""",
}


def main():
    lm = LMStudio()
    meta = targets_meta()
    out = {}
    for sub, sheet in SHEETS.items():
        r = lm.chat_json(SYSTEM, sheet, SCHEMA, max_tokens=8000, temperature=0.4)
        r["subreddit"] = sub
        r["subscribers"] = meta.get(sub, {}).get("subscribers")
        out[sub] = r
        print(json.dumps(r, indent=1), flush=True)
    pathlib.Path("data/out/deep_descriptions.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
