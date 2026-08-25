"""Locate the subreddits whose harvest actually finished."""
from __future__ import annotations

import json
import pathlib

RAW = pathlib.Path("data/raw")
LOG = pathlib.Path("data/meta/harvest_log.jsonl")


def completed(min_posts: int = 200) -> list[str]:
    if not LOG.exists():
        return []
    out = []
    for ln in LOG.read_text().splitlines():
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if r.get("ok") and r.get("posts", 0) >= min_posts:
            out.append(r["subreddit"])
    return out


def path_for(sub: str) -> pathlib.Path:
    return RAW / f"{sub}.posts.jsonl.zst"


def targets_meta() -> dict:
    return {m["display_name"]: m
            for m in json.load(open("data/meta/targets.json"))}
