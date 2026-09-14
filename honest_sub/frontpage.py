"""Which posts stand for "the front page" and "the submission stream" of a month.

Shared by the labeler and the analysis so both select exactly the same posts:
a drift between them would silently pair labels with the wrong population.

  * front page: each UTC day's top n posts by final score, removed posts
    included -- a post removed after reaching the top was still seen.
  * submissions: a seeded random k of ALL the month's posts, drawn from the
    full census, so it covers every hour of the month (the old stratified
    harvests covered only the first hours of each window).
"""
from __future__ import annotations

import datetime as dt
import random
from collections import defaultdict


def day_of(p) -> dt.date:
    return dt.datetime.fromtimestamp(p["created_utc"], dt.timezone.utc).date()


def top_of_days(posts, n: int) -> dict[dt.date, list[dict]]:
    by = defaultdict(list)
    for p in posts:
        by[day_of(p)].append(p)
    return {d: sorted(ps, key=lambda p: (-(p.get("score") or 0),
                                         -(p.get("num_comments") or 0), p["id"]))[:n]
            for d, ps in sorted(by.items())}


def month_sample(posts, sub: str, month: str, k: int) -> list[dict]:
    if k <= 0:
        return []
    pool = sorted(posts, key=lambda p: p["id"])
    return random.Random(f"{sub}-{month}-sample").sample(pool, min(k, len(pool)))
