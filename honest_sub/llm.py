"""Client for LM Studio's OpenAI-compatible server running on the Windows host.

WSL2 in NAT mode cannot reach the Windows host on its gateway address when the
Hyper-V firewall is on (`firewall=true` in .wslconfig) -- but the host's LAN
address works.  That address comes from DHCP and can change, so rather than
hard-coding it we probe the host's interfaces and cache whatever answers.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time

import requests

class Truncated(RuntimeError):
    """Generation hit max_tokens. Content may be absent OR partial.

    Partial content is the dangerous case: it is a valid string but invalid
    JSON, so without this it surfaces far away as a JSONDecodeError rather than
    as the budget problem it is -- which killed a 5-hour overnight run.
    """


MODEL = "google/gemma-4-26b-a4b-qat"
PORT = int(os.environ.get("LMS_PORT", "1234"))
CACHE = pathlib.Path.home() / ".cache" / "honest_sub_lms_endpoint"
IPCONFIG = "/mnt/c/Windows/System32/ipconfig.exe"


def _windows_ips() -> list[str]:
    try:
        out = subprocess.run([IPCONFIG], capture_output=True, text=True, timeout=25).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    ips = []
    for ln in out.replace("\r", "").splitlines():
        if "IPv4 Address" in ln and ":" in ln:
            ips.append(ln.split(":", 1)[1].strip())
    return ips


def _alive(base: str, timeout: float = 5) -> bool:
    try:
        r = requests.get(f"{base}/v1/models", timeout=timeout)
        return r.ok and "data" in r.json()
    except (requests.RequestException, ValueError):
        return False


def discover(force: bool = False) -> str:
    """Return a working base URL for the LM Studio server."""
    if not force and CACHE.exists():
        cached = CACHE.read_text().strip()
        if cached and _alive(cached):
            return cached
    env = os.environ.get("LMS_BASE")
    candidates = ([env] if env else []) + [f"http://127.0.0.1:{PORT}"] + [
        f"http://{ip}:{PORT}" for ip in _windows_ips()
    ]
    for base in candidates:
        if base and _alive(base):
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(base)
            return base
    raise RuntimeError(
        "No LM Studio server found. Check it is running (`lms status` on Windows) "
        "and that its Developer tab is set to serve on the local network."
    )


class LMStudio:
    def __init__(self, model: str = MODEL, base: str | None = None, timeout: int = 900):
        self.base = base or discover()
        self.model = model
        self.timeout = timeout
        self.s = requests.Session()

    def chat(self, system: str, user: str, temperature: float = 0.2,
             max_tokens: int = 3000, json_schema: dict | None = None,
             retries: int = 3, want_reasoning: bool = False):
        """Gemma 4 is a reasoning model: it spends part of `max_tokens` on
        `reasoning_content` before emitting any answer.  Budget generously --
        too small a cap returns an empty string rather than an error."""
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "honest_name", "strict": True,
                                "schema": json_schema},
            }
        last = None
        for attempt in range(retries):
            try:
                r = self.s.post(f"{self.base}/v1/chat/completions",
                                json=payload, timeout=self.timeout)
                if r.status_code >= 500:
                    last = RuntimeError(f"{r.status_code}: {r.text[:300]}")
                    time.sleep(2 * (attempt + 1)); continue
                r.raise_for_status()
                choice = r.json()["choices"][0]
                msg = choice["message"]
                content = (msg.get("content") or "").strip()
                reasoning = (msg.get("reasoning_content") or "").strip()
                if choice.get("finish_reason") == "length":
                    where = "all of it on reasoning" if not content else "mid-output"
                    raise Truncated(
                        f"hit max_tokens={max_tokens} ({where}); raise the budget")
                if not content:
                    raise RuntimeError(f"empty content (finish={choice.get('finish_reason')})")
                return (content, reasoning) if want_reasoning else content
            except requests.RequestException as e:
                last = e
                time.sleep(2 * (attempt + 1))
                # the LAN address may have moved; re-probe once
                if attempt == 1:
                    try:
                        self.base = discover(force=True)
                    except RuntimeError:
                        pass
        raise RuntimeError(f"LM Studio call failed after {retries} attempts: {last}")

    def chat_json(self, system: str, user: str, json_schema: dict, **kw) -> dict:
        txt = self.chat(system, user, json_schema=json_schema, **kw)
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            # structured output occasionally arrives fenced despite the schema
            t = txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
            return json.loads(t.strip())
