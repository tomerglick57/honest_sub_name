"""Thin client for the Arctic Shift Reddit archive API.

Arctic Shift (https://github.com/ArthurHeitmann/arctic_shift) is the successor to
Pushshift.  It ingests posts/comments shortly after they are created, which means
it retains the ORIGINAL text of content that moderators later removed -- the
single most useful signal for detecting what a subreddit actually enforces.
"""
from __future__ import annotations

import time
from typing import Any, Iterator

import requests

BASE = "https://arctic-shift.photon-reddit.com"
MAX_LIMIT = 100  # hard cap enforced server-side


class RateLimited(RuntimeError):
    pass


class ArcticShift:
    """Polite, retrying client.  The API asks for "a couple requests per second"."""

    def __init__(self, min_interval: float = 0.55, timeout: int = 60, retries: int = 5):
        self.min_interval = min_interval
        self.timeout = timeout
        self.retries = retries
        self._last = 0.0
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "honest-sub-name/0.1 (research; subreddit characterisation)"

    def _get(self, path: str, **params: Any) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        backoff = 2.0
        for attempt in range(self.retries):
            gap = self.min_interval - (time.monotonic() - self._last)
            if gap > 0:
                time.sleep(gap)
            self._last = time.monotonic()
            try:
                r = self.s.get(f"{BASE}{path}", params=params, timeout=self.timeout)
            except requests.RequestException as e:
                if attempt == self.retries - 1:
                    raise
                time.sleep(backoff); backoff *= 2
                continue
            if r.status_code == 429:
                time.sleep(float(r.headers.get("X-RateLimit-Reset", backoff)))
                backoff *= 2
                continue
            try:
                body = r.json()
            except ValueError:
                if attempt == self.retries - 1:
                    raise RuntimeError(f"non-JSON from {path}: {r.text[:200]}")
                time.sleep(backoff); backoff *= 2
                continue
            err = body.get("error")
            if err:
                # "Timeout. Maybe slow down a bit" is transient; bad params are not.
                if "imeout" in err or "slow down" in err:
                    time.sleep(backoff); backoff *= 2
                    continue
                raise RuntimeError(f"{path} {params}: {err}")
            return body["data"]
        raise RateLimited(f"gave up on {path} after {self.retries} attempts")

    # ---- subreddit metadata -------------------------------------------------

    def subreddit(self, name: str, fields: str | None = None) -> dict | None:
        d = self._get("/api/subreddits/search", subreddit=name, limit=1, fields=fields)
        return d[0] if d else None

    def top_subreddits(self, min_subscribers: int, limit: int = 100) -> list[dict]:
        """Returns subs with >= min_subscribers, descending.  limit caps at 100."""
        return self._get(
            "/api/subreddits/search",
            min_subscribers=min_subscribers,
            limit=min(limit, MAX_LIMIT),
            fields="display_name,subscribers,over18,public_description,description,created_utc",
        )

    def rules(self, name: str) -> Any:
        return self._get("/api/subreddits/rules", subreddit=name)

    # ---- content ------------------------------------------------------------

    def posts(self, subreddit: str, after: int | str, before: int | str,
              fields: str | None = None, page_size: int = MAX_LIMIT) -> Iterator[dict]:
        """Walk posts in [after, before) ascending, paginating on created_utc.

        The API only sorts by date, so this is the only way to traverse.  We step
        `after` forward past the last item of each page; ties on the same second
        are de-duplicated by id.
        """
        seen: set[str] = set()
        cursor = after
        while True:
            batch = self._get("/api/posts/search", subreddit=subreddit, after=cursor,
                              before=before, limit=page_size, sort="asc", fields=fields)
            if not batch:
                return
            fresh = [p for p in batch if p["id"] not in seen]
            for p in fresh:
                seen.add(p["id"])
                yield p
            last = batch[-1]["created_utc"]
            if len(batch) < page_size:
                return
            # advance; if a whole page shares one timestamp we must step past it
            cursor = last if fresh else last + 1

    def comments(self, subreddit: str, after: int | str, before: int | str,
                 fields: str | None = None, page_size: int = MAX_LIMIT) -> Iterator[dict]:
        seen: set[str] = set()
        cursor = after
        while True:
            batch = self._get("/api/comments/search", subreddit=subreddit, after=cursor,
                              before=before, limit=page_size, sort="asc", fields=fields)
            if not batch:
                return
            fresh = [c for c in batch if c["id"] not in seen]
            for c in fresh:
                seen.add(c["id"])
                yield c
            last = batch[-1]["created_utc"]
            if len(batch) < page_size:
                return
            cursor = last if fresh else last + 1
