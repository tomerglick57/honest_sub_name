"""Stratified sampling of a subreddit's posts into a compact local corpus.

Why stratified: the archive API can only sort by date, so there is no cheap
"top posts of all time" query.  Instead we cut the subreddit's lifetime into
windows and pull a fixed quota from each.  That buys two things a naive
"last N posts" scrape does not:

  * an unbiased view of ordinary content, not just what went viral, and
  * drift over time -- r/conspiracy in 2012 is a different place than in 2024,
    and the honest name should reflect what it is *now*.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
from dataclasses import dataclass, asdict

import zstandard as zstd

from .arctic import ArcticShift

# Keep only the fields that carry signal; full posts are ~112 fields, mostly chaff.
#
# NOTE: these are projected CLIENT-side, not via the API's `fields` parameter.
# That parameter accepts only a short whitelist which excludes the single most
# important field for this project -- `removed_by_category`, which is present in
# full responses but rejected as a selector.  Full responses cost ~4.8 KB/post
# versus ~1.3 KB slim, which is cheap next to losing the moderation signal.
POST_KEEP = (
    "id", "created_utc", "title", "selftext", "author", "score", "num_comments",
    "upvote_ratio", "link_flair_text", "domain", "url", "over_18",
    "removed_by_category", "removed_by", "distinguished", "stickied", "locked",
    "subreddit_subscribers", "is_self", "num_crossposts",
)
COMMENT_KEEP = (
    "id", "created_utc", "body", "author", "score", "parent_id", "link_id",
    "author_flair_text", "distinguished", "stickied",
)

SELFTEXT_CAP = 4000  # characters; long copypasta adds tokens, not signal


@dataclass
class Window:
    start: int
    end: int
    label: str


def windows(first_year: int, last_year: int, per_year: int = 4) -> list[Window]:
    """Quarterly windows across the requested span."""
    out: list[Window] = []
    step = 12 // per_year
    for y in range(first_year, last_year + 1):
        for m in range(1, 13, step):
            s = dt.datetime(y, m, 1, tzinfo=dt.timezone.utc)
            e_m, e_y = m + step, y
            if e_m > 12:
                e_m, e_y = e_m - 12, y + 1
            e = dt.datetime(e_y, e_m, 1, tzinfo=dt.timezone.utc)
            out.append(Window(int(s.timestamp()), int(e.timestamp()), s.strftime("%Y-Q%m")))
    return out


def _project(p: dict, keep: tuple[str, ...] = POST_KEEP) -> dict:
    out = {k: p.get(k) for k in keep}
    st = out.get("selftext") or ""
    if len(st) > SELFTEXT_CAP:
        out["selftext"] = st[:SELFTEXT_CAP] + "…[trunc]"
    return out


def harvest_subreddit(api: ArcticShift, name: str, out_dir: pathlib.Path,
                      years_back: int = 3, quota_per_window: int = 250,
                      per_year: int = 4, today: dt.date | None = None) -> dict:
    """Write data/raw/<name>.posts.jsonl.zst and return a harvest summary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    today = today or dt.datetime.now(dt.timezone.utc).date()
    now_ts = int(dt.datetime(today.year, today.month, today.day,
                             tzinfo=dt.timezone.utc).timestamp())
    wins = [w for w in windows(today.year - years_back, today.year, per_year)
            if w.start < now_ts]

    path = out_dir / f"{name}.posts.jsonl.zst"
    n = 0
    per_window: dict[str, int] = {}
    cctx = zstd.ZstdCompressor(level=10)
    with open(path, "wb") as fh, cctx.stream_writer(fh) as w:
        for win in wins:
            got = 0
            for post in api.posts(name, win.start, win.end):
                w.write((json.dumps(_project(post), ensure_ascii=False) + "\n").encode())
                got += 1
                n += 1
                if got >= quota_per_window:
                    break
            per_window[win.label] = got

    return {
        "subreddit": name,
        "posts": n,
        "windows": len(wins),
        "per_window": per_window,
        "path": str(path),
        "bytes": path.stat().st_size,
    }


def read_posts(path: pathlib.Path):
    """Stream posts back out of a harvested file.

    Tolerates a truncated tail so a file can be read while it is still being
    written -- the harvester appends for ~25 s per subreddit and we want to
    inspect partial output without waiting for it to finish.
    """
    dctx = zstd.ZstdDecompressor()
    with open(path, "rb") as fh, dctx.stream_reader(fh) as r:
        buf = b""
        while True:
            try:
                chunk = r.read(1 << 20)
            except zstd.ZstdError:
                break  # frame still mid-write
            if not chunk:
                break
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for ln in lines:
                if ln:
                    yield json.loads(ln)
        if buf.strip():
            try:
                yield json.loads(buf)
            except json.JSONDecodeError:
                pass  # incomplete final record
