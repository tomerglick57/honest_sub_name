"""Render a subreddit's statistics into a compact evidence sheet for the model.

Everything here is about token economy and auditability.  The model never sees
raw posts; it sees a structured page of measurements.  Every claim it makes can
then be traced back to a number on this sheet.
"""
from __future__ import annotations

import datetime as dt
import pathlib
from collections import Counter

from .signals import profile, log_odds_prior


def build_background(paths: list[pathlib.Path]) -> Counter:
    """Pooled vocabulary across all harvested subs, used as the log-odds baseline."""
    bg = Counter()
    for p in paths:
        bg.update(profile(p)["kept_words"])
    return bg


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "—"


def render(name: str, meta: dict, prof: dict, background: Counter,
           n_titles: int = 25) -> str:
    if not prof.get("posts"):
        return f"# r/{name}\n\n(no posts harvested)"

    n = prof["posts"]
    lines: list[str] = []
    A = lines.append

    A(f"# r/{name}")
    A(f"subscribers: {meta.get('subscribers', 0):,}")
    claim = (meta.get("public_description") or "").strip().replace("\n", " ")
    A(f'STATED PURPOSE (sidebar): "{claim[:400] or "(none set)"}"')
    A("")

    span = ""
    if prof.get("first_utc") and prof.get("last_utc"):
        f = dt.datetime.fromtimestamp(prof["first_utc"], dt.timezone.utc).date()
        l = dt.datetime.fromtimestamp(prof["last_utc"], dt.timezone.utc).date()
        span = f", {f} to {l}"
    A(f"## Sample\n{n:,} posts sampled evenly across quarterly windows{span}")
    A("")

    A("## Moderation")
    rem = prof["removal"]
    A(f"moderator-removed: {_pct(rem.get('moderator', 0), n)}  "
      f"(admin/reddit: {_pct(rem.get('reddit', 0), n)}, "
      f"author-deleted: {_pct(rem.get('deleted', 0), n)})")
    A("")

    A("## Distinctive vocabulary (log-odds vs the other 100 large subs)")
    A(", ".join(w for w, _, _ in log_odds_prior(prof["kept_words"], background, top=30)))
    A("")

    rw = prof["removed_words"]
    if sum(rw.values()) > 400:
        A("## Vocabulary of MODERATOR-REMOVED posts (vs this sub's surviving posts)")
        A("i.e. what topics get taken down here")
        A(", ".join(w for w, _, _ in log_odds_prior(rw, prof["kept_words"], top=22)))
        A("")

    if prof["flairs"]:
        tot = sum(c for _, c in prof["flairs"])
        A("## Flair distribution")
        A(", ".join(f"{f} {_pct(c, n)}" for f, c in prof["flairs"][:12]))
        A("")

    if prof["hosts"]:
        A("## Outbound link sources")
        A(", ".join(f"{h} ({c})" for h, c in prof["hosts"][:18]))
        A("")

    A("## Participation")
    A(f"{prof['unique_authors']:,} distinct authors; top 20 produce "
      f"{prof['top20_author_share']:.1%} of posts")
    A("")

    drift = prof["titles_by_year"]
    if len(drift) > 1:
        A("## Drift (top title terms by year)")
        for y in sorted(drift):
            top = [w for w, _ in drift[y].most_common(10)]
            A(f"  {y}: {', '.join(top)}")
        A("")

    A(f"## Sample surviving titles ({n_titles})")
    for t in prof["sample_kept_titles"][:n_titles]:
        A(f"  - {t[:150]}")
    A("")

    rt = prof["sample_removed_titles"][:n_titles]
    if rt:
        A(f"## Sample MODERATOR-REMOVED titles ({len(rt)})")
        for t in rt:
            A(f"  - {t[:150]}")
    return "\n".join(lines)
