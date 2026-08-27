"""Detect asymmetric moderation: is one side of a debate removed more than the other?

This is a different question from `gap.py`, which measures how much a subreddit
gatekeeps its own subject.  Here we ask whether moderators apply that gate
evenly to competing positions -- the r/conspiracy case, where a neutral-sounding
name hosts a community with a consistent political lean.

Stance is classified by the language model, not by embeddings.  Sentence
embeddings encode topic, not position: measured on a probe set, "Trump is a hero
who saved America" and "Trump is a criminal who destroyed democracy" project to
-0.0098 and -0.0096 on a left/right axis -- indistinguishable, and 2/6 accuracy
overall, which is chance.  Any asymmetry computed that way would be noise
dressed as a finding.
"""
from __future__ import annotations

import json
import math
import random
from collections import Counter

from .llm import Truncated

AXES = {
    "us_politics": {
        "name": "US political lean",
        "left": "expresses a LEFT-leaning view: critical of Trump, Republicans, "
                "conservatives, or sympathetic to Democrats, progressives, the left",
        "right": "expresses a RIGHT-leaning view: critical of Biden, Democrats, "
                 "liberals, or sympathetic to Trump, Republicans, the right",
    },
    "israel_palestine": {
        "name": "Israel/Palestine lean",
        "left": "sympathetic to PALESTINIANS: critical of Israel, the IDF, "
                "Zionism, the occupation, or supportive of Palestinian rights",
        "right": "sympathetic to ISRAEL: critical of Hamas or Palestinian "
                 "militancy, or supportive of Israeli security and statehood",
    },
}

SYSTEM = """\
You label the political stance of Reddit post titles. You will be given a
numbered list. For each one, output its number and exactly one label.

Labels:
  A  = {a}
  B  = {b}
  N  = political/topical but takes no clear side, or is a neutral news headline
  X  = not about this subject at all

Judge only what the title itself expresses. Do not guess from the subreddit it
came from, and do not infer a side from mere mention of a person or group --
"Trump signs executive order" is N, not a side. If you are unsure, answer N.
Label every item. Output nothing but the labels."""

SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "i": {"type": "integer"},
                    "label": {"type": "string", "enum": ["A", "B", "N", "X"]},
                },
                "required": ["i", "label"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["labels"],
    "additionalProperties": False,
}


# Temperature 0.6, not 0. Measured on a fixed batch: at 0.0 and 0.2 the model
# spent an entire 12k budget on reasoning and emitted nothing, twice; at 0.6 it
# answered in 32s. Greedy decoding sends this model into degenerate reasoning
# loops, so labels are sampled and their stability is measured instead.
CLASSIFY_TEMPERATURE = 0.6


def classify_batch(lm, titles: list[str], axis: str, max_tokens: int = 12000,
                   max_attempts: int = 3, temperature: float = CLASSIFY_TEMPERATURE
                   ) -> list[str]:
    """Label a batch of titles. Falls back to "N" for anything the model omits.

    Batch size trades throughput against reasoning overrun: the model thinks
    proportionally longer about longer lists, and 25 titles reliably exhausted
    a 6k budget before producing any output.  Twelve fits comfortably.
    """
    ax = AXES[axis]
    sys_prompt = SYSTEM.format(a=ax["left"], b=ax["right"])
    listing = "\n".join(f"{i}. {t[:220]}" for i, t in enumerate(titles))
    budget = max_tokens
    out = None
    for attempt in range(max_attempts):
        try:
            out = lm.chat_json(sys_prompt, listing, SCHEMA,
                               max_tokens=budget, temperature=temperature)
            break
        except (Truncated, json.JSONDecodeError):
            # Truncated output arrives either as an explicit budget error or as
            # unparseable JSON; both mean "generate again with more room".
            if attempt == max_attempts - 1:
                raise
            budget *= 2
    if out is None:
        raise RuntimeError("classification produced no parseable output")
    got = {d["i"]: d["label"] for d in out.get("labels", [])}
    return [got.get(i, "N") for i in range(len(titles))]


# ---- statistics -------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval; behaves sensibly at small n and rates near 0 or 1."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _logfact(n: int, _c: dict = {}) -> float:
    if n not in _c:
        _c[n] = math.lgamma(n + 1)
    return _c[n]


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """p-value for the 2x2 table [[a,b],[c,d]] without needing scipy."""
    n = a + b + c + d
    r1, r2, c1 = a + b, c + d, a + c

    def prob(x: int) -> float:
        y, z_, w = r1 - x, c1 - x, r2 - (c1 - x)
        if min(y, z_, w) < 0:
            return 0.0
        return math.exp(_logfact(r1) + _logfact(r2) + _logfact(c1) + _logfact(n - c1)
                        - _logfact(n) - _logfact(x) - _logfact(y)
                        - _logfact(z_) - _logfact(w))

    p_obs = prob(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    total = 0.0
    for x in range(lo, hi + 1):
        px = prob(x)
        if px <= p_obs * 1.000001:
            total += px
    return min(1.0, total)


def asymmetry(labels: list[str], removed: list[bool]) -> dict:
    """Removal rate for stance A vs stance B, with a Fisher test on the difference."""
    a_rm = sum(1 for l, r in zip(labels, removed) if l == "A" and r)
    a_n = sum(1 for l in labels if l == "A")
    b_rm = sum(1 for l, r in zip(labels, removed) if l == "B" and r)
    b_n = sum(1 for l in labels if l == "B")
    pa = a_rm / a_n if a_n else 0.0
    pb = b_rm / b_n if b_n else 0.0
    return {
        "n_A": a_n, "removed_A": a_rm, "rate_A": round(pa, 4), "ci_A": wilson(a_rm, a_n),
        "n_B": b_n, "removed_B": b_rm, "rate_B": round(pb, 4), "ci_B": wilson(b_rm, b_n),
        "diff": round(pa - pb, 4),
        "ratio": round(pa / pb, 3) if pb else None,
        # Under case-control sampling (all removed posts + a sample of kept
        # ones) the raw rates are inflated, but the odds ratio is unaffected:
        # the sampling fraction cancels.  It is the estimate to trust here.
        "odds_ratio": (round((a_rm * (b_n - b_rm)) / ((a_n - a_rm) * b_rm), 3)
                       if (a_n - a_rm) and b_rm else None),
        "p_fisher": fisher_exact_two_sided(a_rm, a_n - a_rm, b_rm, b_n - b_rm),
        "label_mix": dict(Counter(labels)),
    }


def permutation_p(labels: list[str], removed: list[bool], n_iter: int = 5000,
                  seed: int = 0) -> float:
    """How often does shuffling the stance labels reproduce the observed gap?

    The control for the whole method: if the classifier is picking up noise, a
    shuffled assignment produces the same asymmetry just as often.
    """
    pairs = [(l, r) for l, r in zip(labels, removed) if l in ("A", "B")]
    if not pairs:
        return 1.0
    obs = abs(asymmetry([l for l, _ in pairs], [r for _, r in pairs])["diff"])
    ls = [l for l, _ in pairs]
    rs = [r for _, r in pairs]
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_iter):
        rng.shuffle(ls)
        if abs(asymmetry(ls, rs)["diff"]) >= obs:
            hits += 1
    return (hits + 1) / (n_iter + 1)
