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
  the sub does what it says, set gap_severity to "none". A boring accurate
  verdict is far more valuable than a manufactured controversy.
- Even when gap_severity is "none", the honest name must still be DESCRIPTIVE.
  Never answer with the subreddit's own name, and never prefix it with "r/".
  For an accurate sub, describe what it is: r/aww -> "Cute Animal Photo Feed",
  not "r/aww".
- Distinguish topic drift ("Unpopular Opinions" is mostly political) from
  editorial slant (one viewpoint is removed and another is not). Only claim
  slant when the removal evidence supports it.
- Removal rate alone is not bias. Large subs remove heavily for spam and
  low-effort content. Look at WHAT is removed, not just how much.
- READ THE REMOVED TITLES before claiming a viewpoint is suppressed. The removed
  VOCABULARY list is ambiguous on its own: a word appears there because posts
  *mentioning* that topic were removed, which tells you nothing about which side
  of it was being argued. A sub that removes posts criticising a figure and a sub
  that removes posts praising them produce the identical word in that list.
- Therefore: only claim a viewpoint is suppressed if the removed TITLES visibly
  express that viewpoint. If the removed titles argue the same line the sub is
  supposed to favour, the removals are about spam, duplicates, off-topic content
  or meta-criticism -- say that instead. Getting this backwards is the single
  worst error you can make here.
- A low moderator-removal rate (under ~10%) is weak ground for any claim about
  editorial slant. Lower your confidence accordingly.
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
        # An enum, not a number: LM Studio's constrained decoding enforces
        # types and enum membership but NOT numeric bounds, so a `number` field
        # documented as "0.0 to 1.0" came back as 4 and 5 in 95 of 100 runs.
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "how well the sheet supports this verdict",
        },
    },
    "required": ["honest_name", "honest_description", "gap_severity",
                 "gap_summary", "evidence", "what_gets_removed", "confidence"],
    "additionalProperties": False,
}


def name_subreddit(lm, sheet: str, max_tokens: int = 8000,
                   max_attempts: int = 3) -> dict:
    """Name one subreddit, escalating the token budget if reasoning overruns.

    Gemma 4 spends an unpredictable share of `max_tokens` on reasoning before
    emitting any answer, and a dense evidence sheet can push it past the cap --
    the same subreddit may fit on one run and overrun on the next.  Rather than
    setting one huge budget for every call, start moderate and double on the
    specific failure.
    """
    budget = max_tokens
    last = None
    for _ in range(max_attempts):
        try:
            return lm.chat_json(SYSTEM, sheet, SCHEMA,
                                max_tokens=budget, temperature=0.3)
        except RuntimeError as e:
            if "went to reasoning" not in str(e):
                raise
            last = e
            budget *= 2
    raise RuntimeError(f"still overrunning at {budget // 2} tokens: {last}")
