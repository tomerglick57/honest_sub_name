"""Client for TypeSafe's System One API (Jev): typed answers, not text.

POST https://api.typesafe.ai/v1/systemone with a `state` (the text) and a map
of typed `questions`; a Choice question returns the picked option plus a
probability over all options. Priced per input token only (models page,
2026-09-17: $0.042 / Mtok, 1,200 req/min), so one request per title is fine.

The key is read from TYPESAFE_API_KEY, else from a `TYPESAFE_API_KEY=...`
line in the repo's .env (gitignored).
"""
from __future__ import annotations

import os
import pathlib
import random
import time

import requests

BASE = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
ROOT = pathlib.Path(__file__).resolve().parent.parent


def api_key() -> str:
    k = os.environ.get("TYPESAFE_API_KEY")
    if not k and (ROOT / ".env").exists():
        for ln in (ROOT / ".env").read_text().splitlines():
            if ln.strip().startswith("TYPESAFE_API_KEY="):
                k = ln.split("=", 1)[1].strip().strip("'\"")
    if not k:
        raise RuntimeError("no TypeSafe key: set TYPESAFE_API_KEY or add it to .env")
    return k


class TypeSafe:
    def __init__(self, model: str = "jev-latest", timeout: int = 60, retries: int = 6):
        self.model, self.timeout, self.retries = model, timeout, retries
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {api_key()}"

    def models(self) -> dict:
        r = self.s.get(f"{BASE}/v1/models", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def ask(self, state, questions: dict) -> dict:
        """Return the raw response (model, answers, usage). Backs off on 429/529."""
        payload = {"state": state, "model": self.model, "questions": questions}
        last = None
        for attempt in range(self.retries):
            try:
                r = self.s.post(f"{BASE}/v1/systemone", json=payload, timeout=self.timeout)
            except requests.RequestException as e:
                last = e; time.sleep(min(30, 2 ** attempt) + random.random()); continue
            if r.status_code in (429, 529) or r.status_code >= 500:
                last = RuntimeError(f"{r.status_code}: {r.text[:200]}")
                time.sleep(min(30, 2 ** attempt) + random.random()); continue
            if not r.ok:
                raise RuntimeError(f"{r.status_code}: {r.text[:400]}")
            return r.json()
        raise RuntimeError(f"TypeSafe call failed after {self.retries} attempts: {last}")
