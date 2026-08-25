"""Ask the local model for an honest name, grounded in the evidence sheet."""
from __future__ import annotations

SYSTEM = """\
You are a research analyst characterising online communities. You are given a
statistical evidence sheet about one subreddit: what it says it is, what gets
posted, and what its moderators remove.

Your job is to write an HONEST NAME and HONEST DESCRIPTION: what this community
actually is in practice, as opposed to what its name and sidebar claim.

Rules:
- Ground every judgement in the numbers on the sheet. Never invent a statistic.
- The honest name is only interesting when it DIFFERS from the literal name. If
  the sub does what it says, say so plainly and set gap_severity to "none". A
  boring accurate verdict is far more valuable than a manufactured controversy.
- Distinguish topic drift ("Unpopular Opinions" is mostly political) from
  editorial slant (one viewpoint is removed and another is not). Only claim
  slant when the removal evidence supports it.
- Removal rate alone is not bias. Large subs remove heavily for spam and
  low-effort content. Look at WHAT is removed, not just how much.
- Be specific and neutral. "US partisan politics" beats "right-wing garbage".
- If the evidence is thin or ambiguous, lower your confidence and say why.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "honest_name": {
            "type": "string",
            "description": "Short honest name, under 60 characters",
        },
        "honest_description": {
            "type": "string",
            "description": "Two or three sentences on what this community actually is",
        },
        "gap_severity": {
            "type": "string",
            "enum": ["none", "mild", "moderate", "severe"],
            "description": "How far the reality is from what the name implies",
        },
        "gap_summary": {
            "type": "string",
            "description": "One sentence: the difference between claim and reality",
        },
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-6 bullets, each citing a specific figure from the sheet",
        },
        "what_gets_removed": {
            "type": "string",
            "description": "What the moderators actually suppress, or 'unclear'",
        },
        "confidence": {"type": "number", "description": "0.0 to 1.0"},
    },
    "required": ["honest_name", "honest_description", "gap_severity",
                 "gap_summary", "evidence", "what_gets_removed", "confidence"],
    "additionalProperties": False,
}


def name_subreddit(lm, sheet: str, max_tokens: int = 4000) -> dict:
    return lm.chat_json(SYSTEM, sheet, SCHEMA, max_tokens=max_tokens, temperature=0.3)
