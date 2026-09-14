"""Topic + US-stance labels for post titles, tuned for throughput.

One pass gives each title one of four labels: O (not political), P (political,
no US-partisan side), L, R. The political share -- everything that is not O --
is the load-bearing quantity; the L/R split is a secondary layer with
measurably noisier boundaries.

Measured on gemma-4-31b-qat at 192.168.1.185 (2026-09-12):
  * reasoning_effort="none" cut a 20-title batch from 204 s to 47 s with
    identical labels; reasoning was ~75% of all output tokens.
  * a keyed-object schema ({"0": "O", "1": "P", ...}, every key required)
    halves output tokens against [{"i": 0, "l": "O"}, ...], and constrained
    decoding must emit every index, so an item cannot be silently dropped.
  * temperature 0 without reasoning does not loop (the loops lived in the
    reasoning channel); two passes agreed on 79/80 titles.
  * against the earlier 26B stance labels: 93.5% agreement on political vs
    not, 85.5% on the 4-way label (200 titles); disagreement sits mostly on
    the P/L boundary, which is why stance is reported as the secondary layer.
"""
from __future__ import annotations

LABELS = ("O", "P", "L", "R")
MODEL_TAG = "gemma-4-31b-qat/no-reasoning/t0/v1"

SYSTEM = """\
You label Reddit r/pics post titles by subject and US political stance. For each numbered title output exactly one label:
 O = not about politics
 P = about politics, government, political figures, elections, protests, policy, war or international political conflict, but takes no clear US partisan side
 L = takes a US left-leaning side: critical of Trump, Republicans, conservatives, MAGA, or sympathetic to Democrats, progressives, the left
 R = takes a US right-leaning side: critical of Biden, Democrats, liberals, the left, or sympathetic to Trump, Republicans, the right
Judge only what the title itself says. Mere mention of a politician is P, not a side. Label every item."""


def schema(n: int) -> dict:
    return {"type": "object",
            "properties": {str(i): {"type": "string", "enum": list(LABELS)} for i in range(n)},
            "required": [str(i) for i in range(n)],
            "additionalProperties": False}


def label_batch(lm, titles: list[str], max_tokens: int = 3000) -> list[str]:
    listing = "\n".join(f"{i}. {' '.join((t or '').split())[:220]}"
                        for i, t in enumerate(titles))
    out = lm.chat_json(SYSTEM, listing, schema(len(titles)), max_tokens=max_tokens,
                       temperature=0.0, extra={"reasoning_effort": "none"})
    labs = [out.get(str(i)) for i in range(len(titles))]
    if any(l not in LABELS for l in labs):
        raise ValueError(f"schema violated: {labs}")
    return labs
