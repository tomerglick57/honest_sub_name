"""Compute the honesty gap as a measurement rather than asking the model for one.

Asking the model to rate `gap_severity` did not survive contact with the data:
across two runs on identical input, 23 of 100 verdicts changed, and r/stocks
swung from "none" to "severe" purely on temperature. Determinism did not fix it
either -- temperature 0 was stable but wrong, rating r/Fitness "none" while it
removes 77% of posts, targeting `help`, `weight`, `muscle` and `gym`.

So severity is derived here from two reproducible quantities:

  removal weight   how much a sub's moderators take down
  identity match   how closely what they take down resembles what the sub
                   claims to be, by embedding similarity

Heavy removal of off-topic content is ordinary moderation and scores low --
r/worldnews removing `stabbing` and `synagogue` is the system working. Heavy
removal of the sub's OWN subject is the honesty gap: r/Fitness removing
`workout` and `muscle`, r/stocks removing `beginner` and `investing`.

Cosine similarity over short texts occupies a narrow band, so both terms are
converted to percentile ranks within the cohort before being combined; the
score is relative to the other large subreddits, not an absolute.
"""
from __future__ import annotations

import math

import requests

EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
MIN_REMOVED_TOKENS = 300  # below this the removed-word list is too thin to trust


def embed(base: str, texts: list[str], timeout: int = 180) -> list[list[float]]:
    r = requests.post(f"{base}/v1/embeddings",
                      json={"model": EMBED_MODEL, "input": texts}, timeout=timeout)
    r.raise_for_status()
    return [d["embedding"] for d in r.json()["data"]]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def percentile_ranks(values: list[float]) -> list[float]:
    """Fractional rank in [0, 1]; ties share the mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mean_rank = (i + j) / 2
        for k in range(i, j + 1):
            ranks[order[k]] = mean_rank / max(1, len(values) - 1)
        i = j + 1
    return ranks


def severity(score: float, identity_match: float | None) -> str:
    if identity_match is None:
        return "unrated"          # not enough removed content to judge
    if score >= 0.75:
        return "severe"
    if score >= 0.55:
        return "moderate"
    if score >= 0.35:
        return "mild"
    return "none"


def score_cohort(records: list[dict]) -> list[dict]:
    """Given [{sub, mod_removal_rate, identity_match}], attach ranks and severity.

    `identity_match` may be None when a sub removes too little to characterise;
    those are ranked at the cohort median so their removal rate alone does not
    manufacture a gap, and are labelled "unrated".
    """
    rates = [r["mod_removal_rate"] for r in records]
    sims = [r["identity_match"] for r in records]
    known = [s for s in sims if s is not None]
    median = sorted(known)[len(known) // 2] if known else 0.0
    filled = [s if s is not None else median for s in sims]

    rate_rank = percentile_ranks(rates)
    sim_rank = percentile_ranks(filled)
    for r, rr, sr in zip(records, rate_rank, sim_rank):
        # geometric mean: a gap needs BOTH heavy removal and on-topic removal.
        # Either one alone is unremarkable, so a product punishes the lopsided
        # cases that an average would let through.
        r["removal_rank"] = round(rr, 3)
        r["identity_rank"] = round(sr, 3)
        r["gap_score"] = round(math.sqrt(rr * sr), 3)
        r["gap_severity"] = severity(r["gap_score"], r["identity_match"])
    return records
