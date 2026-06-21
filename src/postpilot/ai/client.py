"""Claude client with model-tier routing, prompt caching, and templated fallbacks.

Model IDs per the environment's current Claude lineup:
  Haiku 4.5  -> routine narration (best-time tips, weekly summaries)
  Sonnet 4.6 -> brand-voice copy the user reads/judges (variants, rewrites)
  Opus 4.8   -> premium deep analysis only (top tier, off by default)
Implementer note: confirm exact model IDs/params via the `claude-api` skill before launch.
"""

from __future__ import annotations

import enum

from postpilot.ai import prompts
from postpilot.ai.guardrails import safe_json, sanitize_variants
from postpilot.ai.prompts import BrandProfile
from postpilot.core.config import get_settings
from postpilot.core.logging import get_logger

log = get_logger("ai")


class Tier(str, enum.Enum):
    haiku = "claude-haiku-4-5-20251001"
    sonnet = "claude-sonnet-4-6"
    opus = "claude-opus-4-8"


class AIClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._key = settings.anthropic_api_key
        self._client = None
        if settings.ai_enabled and self._key:
            try:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(api_key=self._key)
            except Exception as e:  # noqa: BLE001
                log.warning("ai.init_failed", error=str(e))
        elif not settings.ai_enabled:
            log.info("ai.disabled")

    @property
    def available(self) -> bool:
        return self._client is not None

    async def _call(self, tier: Tier, system: str, user: str, *, max_tokens: int) -> str | None:
        if not self._client:
            return None
        try:
            resp = await self._client.messages.create(
                model=tier.value,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
            )
            if not resp.content or getattr(resp, "stop_reason", None) == "refusal":
                return None
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        except Exception as e:  # noqa: BLE001 - never let AI break the core flow
            log.warning("ai.call_failed", tier=tier.value, error=str(e))
            return None

    async def generate_variants(
        self, brand: BrandProfile, intent: str, *, n: int = 3, existing: list[str] | None = None,
        allow_emoji: bool = False,
    ) -> list[str]:
        system, user = prompts.variants_prompt(brand, intent, n, existing or [])
        raw = await self._call(Tier.sonnet, system, user, max_tokens=600)
        obj = safe_json(raw) if raw else None
        if obj and isinstance(obj.get("variants"), list):
            return sanitize_variants([str(x) for x in obj["variants"]][:n], allow_emoji=allow_emoji)
        # Fallback: deterministic on-topic templates so the feature never hard-fails.
        base = {"open": "We're open! Come say hi", "close": "We're closed for today - thanks!"}.get(
            intent, intent
        )
        return [base, f"{base} See you soon.", f"{base} 🙂" if allow_emoji else f"{base}."][:n]

    async def rewrite(self, brand: BrandProfile, original: str, adjustment: str) -> str:
        system, user = prompts.rewrite_prompt(brand, original, adjustment)
        raw = await self._call(Tier.sonnet, system, user, max_tokens=200)
        obj = safe_json(raw) if raw else None
        if obj and obj.get("text"):
            return sanitize_variants([str(obj["text"])], allow_emoji=True)[0]
        return original

    async def best_time_tips(self, business_type: str, data: dict) -> dict:
        system, user = prompts.best_time_prompt(business_type, data)
        raw = await self._call(Tier.haiku, system, user, max_tokens=200)
        obj = safe_json(raw) if raw else None
        return obj or {"headline": "Post when your audience is active",
                       "tips": [{"when": "weekday mornings", "why": "higher engagement"}]}

    async def weekly_summary(self, data: dict) -> dict:
        system, user = prompts.weekly_summary_prompt(data)
        raw = await self._call(Tier.haiku, system, user, max_tokens=300)
        obj = safe_json(raw) if raw else None
        sent = data.get("posts_sent", 0)
        return obj or {"summary": f"You posted {sent} times this week.",
                       "suggestion": "Keep a steady posting rhythm."}
