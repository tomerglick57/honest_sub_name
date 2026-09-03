"""Second-pass classifier: does a sided title ADVOCATE its stance, or QUOTE it?

Motivation (docs/audience-methodology.md §10): G1 failed because the stance
classifier labels what the title text expresses, and in in-group spaces a
dominant genre is showcasing the out-group's statements to mock them --
"Biden: 'MAGA Republicans are a threat'" expresses a left view and advocates
nothing. Title-stance != poster-stance under quotation. This pass separates
the two so vote/removal asymmetry can be computed on advocacy posts only.

Mockery is deliberately NOT flipped to the opposite stance: flipping compounds
two error rates. Non-advocacy is dropped from asymmetry analysis instead.
"""
from __future__ import annotations

import json

from .llm import Truncated

SYSTEM = """\
You label how Reddit post titles convey a political position. Every title you
receive was previously judged to express a left- or right-leaning view. Your
job is to decide HOW the title conveys that view. You will be given a numbered
list; for each item output its number and exactly one label.

Labels:
  ADV = the title argues, asserts or frames the view in the poster's OWN voice.
        Slanted news framing counts as ADV: the framing is the poster's.
        Own-voice ridicule of the other side is also ADV.
  QUO = the political view belongs to someone being quoted, reported or
        showcased -- the title's content is a statement BY a politician,
        celebrity or other named figure ("X says...", "X: '...'", "X mocks...").
        This includes showcasing an opponent's statement so readers can ridicule
        it: if the view expressed is the quoted person's, it is QUO.
  UNC = cannot tell from the title alone.

Judge only the title text. Label every item. Output nothing but the labels."""

SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "i": {"type": "integer"},
                    "label": {"type": "string", "enum": ["ADV", "QUO", "UNC"]},
                },
                "required": ["i", "label"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["labels"],
    "additionalProperties": False,
}

# Same operating point as the stance pass: batches of 12 (25 overran reasoning),
# temperature 0.6 (0.0 and 0.2 loop), escalating budget on truncation.
def classify_batch_quote(lm, titles: list[str], max_tokens: int = 12000,
                         max_attempts: int = 3, temperature: float = 0.6) -> list[str]:
    listing = "\n".join(f"{i}. {t[:220]}" for i, t in enumerate(titles))
    budget = max_tokens
    out = None
    for attempt in range(max_attempts):
        try:
            out = lm.chat_json(SYSTEM, listing, SCHEMA,
                               max_tokens=budget, temperature=temperature)
            break
        except (Truncated, json.JSONDecodeError):
            if attempt == max_attempts - 1:
                raise
            budget *= 2
    if out is None:
        raise RuntimeError("quote pass produced no parseable output")
    got = {d["i"]: d["label"] for d in out.get("labels", [])}
    return [got.get(i, "UNC") for i in range(len(titles))]


# Pre-registered probe set; the pass is unusable below 14/16.
PROBES = [
    ("Biden: 'MAGA Republicans attempting to abuse power are a threat to this country'", "QUO"),
    ("Keith Olbermann Says RFK Jr. 'Must Be Forced to Withdraw From the Ballot'", "QUO"),
    ("Kimmel Mocks Concern Over Illegal Immigrant Murderer In Michigan", "QUO"),
    ("Trump: 'I alone can fix the border crisis'", "QUO"),
    ("AOC says billionaires should not exist", "QUO"),
    ("Tucker Carlson claims the border crisis is Biden's deliberate policy", "QUO"),
    ("Sanders: 'The American healthcare system is a cruel joke'", "QUO"),
    ("MTG says Democrats control the weather", "QUO"),
    ("Top 9 'CornPop' Sized Whoppers Biden Told During First Debate", "ADV"),
    ("The GOP has always been the party of billionaires and always will be", "ADV"),
    ("Biden's open border policy is a deliberate betrayal of American workers", "ADV"),
    ("Trump is a criminal who tried to destroy American democracy", "ADV"),
    ("Walz's claim he was in Hong Kong during Tiananmen undercut by unearthed newspaper reports", "ADV"),
    ("Another day, another radical leftist judge legislating from the bench", "ADV"),
    ("How the right-wing media machine manufactures outrage on demand", "ADV"),
    ("Democrats' weather-control conspiracy nonsense shows how unserious this party is", "ADV"),
]


def validate(lm) -> tuple[int, list]:
    titles = [t for t, _ in PROBES]
    got = classify_batch_quote(lm, titles[:8]) + classify_batch_quote(lm, titles[8:])
    misses = [(t, want, g) for (t, want), g in zip(PROBES, got) if g != want]
    return len(PROBES) - len(misses), misses
