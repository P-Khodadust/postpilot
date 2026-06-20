"""Output guardrails: enforce length, strip banned tokens, safe JSON parsing with fallback."""

from __future__ import annotations

import json
import re

MAX_TWEET = 280


def clamp_tweet(text: str) -> str:
    text = text.strip()
    return text if len(text) <= MAX_TWEET else text[: MAX_TWEET - 1].rstrip() + "…"


def safe_json(raw: str) -> dict | None:
    """Parse a model response that should be JSON; tolerate code fences. None on failure."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def sanitize_variants(items: list[str], *, allow_emoji: bool) -> list[str]:
    out = []
    for it in items:
        t = clamp_tweet(it)
        if not allow_emoji:
            t = t.replace("#", "").strip()
        if t:
            out.append(t)
    return out
