"""The honest_sub.topic rubric as a TypeSafe Jev Choice question, one title per call.

Measured on 1,011 r/pics front-page titles (scripts/typesafe_trial.py,
2026-09-17, jev-1.13.0): 25 titles/s at 8 concurrent, ~508 input tokens a
title ($0.021 per 1k). Against gemma-with-reasoning on the 261-title
validation set: 88.9% on political-vs-not, 69.3% 4-way -- Jev calls most
sided titles P. But its confidence is informative: at >= THRESH (78% of
titles) it agrees with production 96%, below it ~50%. Routing the rest to
gemma ("hybrid") scored 97.7% / 87.0% on the same rows, above gemma-fast's
own 96.2% / 86.2%, with a fifth of the LAN calls.
"""
from __future__ import annotations

THRESH = 0.8
TAG_PREFIX = "jev"  # full tag is f"{model}/choice-v1", model from the response

QUESTION = {
    "label": {
        "type": "choice",
        "instructions": ("This is the title of a Reddit r/pics post. Classify its subject and US political "
                         "stance. Judge only what the title itself says. Mere mention of a politician is "
                         "P, not a side."),
        "criteria": {
            "O": {"what": "not about politics"},
            "P": {"what": "about politics, government, political figures, elections, protests, policy, "
                          "war or international political conflict, but takes no clear US partisan side",
                  "not_for": "titles that clearly side with the US left or right"},
            "L": {"what": "takes a US left-leaning side: critical of Trump, Republicans, conservatives, "
                          "MAGA, or sympathetic to Democrats, progressives, the left"},
            "R": {"what": "takes a US right-leaning side: critical of Biden, Democrats, liberals, the "
                          "left, or sympathetic to Trump, Republicans, the right"},
        },
    }
}


def label_one(ts, title: str) -> tuple[str, float, str]:
    """Return (label, confidence, model_tag) for one title."""
    resp = ts.ask(" ".join((title or "").split())[:220] or "(untitled)", QUESTION)
    a = resp["answers"]["label"]
    return a["choice"], float(a.get("confidence", 0.0)), f"{resp.get('model', 'jev')}/choice-v1"
