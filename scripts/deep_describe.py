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
Write neutrally and specifically. The honest_name must be a DESCRIPTIVE phrase
for what the community actually is -- never the subreddit's own name, never
prefixed with "r/" (e.g. "US Geopolitics Feed", not "r/worldnews"). Output JSON."""

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
- Retention: the one gate with any asymmetry, and it is weak. Among established regulars whose posts SURVIVE, left advocates return at 76% vs 86% for right (p=0.03 -- suggestive only; the raw gap was partly drive-by visitors). The lean is maintained mostly by who shows up, possibly amplified by who stays.
- Genre: argues in its own voice; quotation of public figures is rare (<=9%).""",
"Conservative": """# r/Conservative (1.20M subscribers; sidebar: forum for conservatives)
MEASURED FUNNEL (2,076 case-control + 4,600 survivor stance labels):
- Posted content: right-leaning outnumbers left 4.3:1 (557 vs 129 sided).
- Moderators: remove left-advocacy posts at 69.6% vs 46.0% for right (OR=2.68, p=7.6e-11).
- Voters: bury surviving left advocacy (rank-biserial -0.115, p=0.019).
- Self-deletion: left posters withdraw their own posts at 3.3x the odds (deleted posts are 30% left vs 11% of kept, p=3.3e-05) -- a pile-on signature.
- Retention (visitor-controlled): among established REGULARS whose posts were removed, left advocates return at 57% vs 82% for right (p=4.7e-06) -- genuine chilling of regulars, not just visitors leaving. Left advocates are also more often visitors in the first place (29% vs 12%).
- Genre: 29% of surviving left-labelled posts are quotations of left figures showcased for the in-group; these dominate the top-scored "left" posts. Mock-quotation is the community's upvoted mode of engaging opponents.
- Note: the sub openly declares itself conservative; the finding is HOW the uniformity is produced -- by all four gates at once.""",
"politics": """# r/politics (8.4M subscribers; name implies general US politics forum; sidebar: news and discussion about US politics)
MEASURED FUNNEL (8,004 stance-classified posts):
- Posted content: left-leaning outnumbers right 3.6:1 (1371 vs 377 sided).
- Moderators: remove right-advocacy posts at 63.2% vs 40.6% for left (OR=0.40, p=2.7e-12). Source-quality rules were tested and do NOT explain this: removed posts are ~21% mainstream-sourced and kept ~38%, identically for both stances.
- Voters: bury surviving right content massively -- median percentile 0.13 vs 0.70 for left (rank-biserial 0.757, p=8.7e-38); of survivors reaching the top score decile, 142 are left vs 1 right.
- Combined visibility: after moderation and voting, the visible sub is ~96% left.
- Retention (visitor-controlled): right-advocacy REGULARS return less even when their posts were kept (82% vs 93%, p=6.4e-4). Right advocates are also twice as often drive-by visitors (24% vs 13%).
- Self-deletion: right posters withdraw their own posts at ~2x odds (OR 0.51, p=0.047 -- marginal, treat as suggestive).""",
"PublicFreakout": """# r/PublicFreakout (4.7M subscribers; sidebar: "people freaking out, melting down, losing their cool, or being weird in public" -- no political mandate)
MEASURED FUNNEL (3,804 stance-classified posts, 2023-2026):
- Posted content: 92% of posts are not politically sided at all (street fights, meltdowns, arguments). Among the sided 8%, LEFT outnumbers right 5.9:1 (242 vs 41) -- the most lopsided composition of any audited sub.
- Moderators: no significant stance asymmetry (advocacy-only OR=0.61, p=0.20). Removal is direction-neutral.
- Voters: bury surviving right advocacy hard -- median percentile 0.17 vs 0.64 for left (rank-biserial 0.63, p=1.8e-05).
- Retention (visitor-controlled): right-advocacy REGULARS return at 47% vs 86% for left even when their posts were kept (p=0.001); visitor shares are equal (22% both sides), so this is not a visitor artifact.
- Self-deletion: no significant asymmetry (p=0.27).""",
"pics": """# r/pics, 2025-2026 era only (31M subscribers; sidebar: "a place for photographs, pictures, and other images")
MEASURED (3,804 stance-classified 2025-26 posts + keyword trend on 2023-26):
- The sub CHANGED in 2025: moderator removal tripled from ~14% to ~46% of all submissions and stayed there; in 2025-26 removals now outnumber keeps (6,079 vs 5,369 in the deep sample).
- Politicization is in the votes, not the submissions: political content is only ~5% of what is posted but rose from 3% of the top score decile in 2023 to 33% in 2026 (keyword screen). The front page turned into political photojournalism; the submission stream did not.
- Explicit ADVOCACY remains rare: only 1.8% of classified posts take a side (49 left vs 18 right).
- Moderation shows no directional stance bias (OR=0.78, p=0.78); the heavy removal is direction-neutral volume control.
- Vote direction and retention: sided sample too small to measure (right n=6); no directional claim is supported either way.
- The pooled 3-year ledger verdict ("no gap") is accurate for 2023-24 and misleading for 2025-26.""",
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
