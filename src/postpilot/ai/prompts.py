"""Prompt builders. Stats are computed in code and passed as DATA; the model only narrates."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class BrandProfile:
    business_name: str
    business_type: str
    tone_words: list[str]
    sample_posts: list[str]
    avoid: list[str]

    def to_block(self) -> str:
        return (
            "BRAND PROFILE (stable):\n"
            f"- Business: {self.business_name} ({self.business_type})\n"
            f"- Tone: {', '.join(self.tone_words) or 'friendly, plain, confident'}\n"
            f"- Avoid: {', '.join(self.avoid) or 'hashtags, emoji walls, clichés'}\n"
            f"- Examples of their voice: {json.dumps(self.sample_posts[:3])}\n"
        )


GUARDRAILS = (
    "RULES: Write as the owner, not an ad. Each post <= 280 characters. "
    "Never invent a number, percentage, or claim not present in DATA. "
    "No hashtags or emoji unless the brand profile opts in. Return ONLY valid JSON."
)


def variants_prompt(brand: BrandProfile, intent: str, n: int, existing: list[str]) -> tuple[str, str]:
    system = brand.to_block() + "\n" + GUARDRAILS
    user = (
        f"Write {n} distinct ways to say '{intent}' for this business. "
        f"Vary structure and opening. Avoid repeating these existing ones: {json.dumps(existing)}. "
        'Return JSON: {"variants": ["...", "..."]}'
    )
    return system, user


def rewrite_prompt(brand: BrandProfile, original: str, adjustment: str) -> tuple[str, str]:
    system = brand.to_block() + "\n" + GUARDRAILS
    user = (
        f"Rewrite this post to be {adjustment}. Keep the same meaning and any specific details; "
        f'change only the style. Original: {json.dumps(original)}. Return JSON: {{"text": "..."}}'
    )
    return system, user


def best_time_prompt(business_type: str, data: dict) -> tuple[str, str]:
    system = (
        "Turn this performance table into 2-3 short, friendly tips for a busy "
        f"{business_type} owner. Only use numbers present in DATA. No new stats. <= 60 words total. "
        'Return JSON: {"headline": "...", "tips": [{"when": "...", "why": "..."}]}'
    )
    user = "DATA:\n" + json.dumps(data, default=str)
    return system, user


def weekly_summary_prompt(data: dict) -> tuple[str, str]:
    system = (
        "Summarize this week for a busy business owner in <= 90 words. Friendly, concrete, "
        "no invented numbers - only DATA. End with one specific suggestion. "
        'Return JSON: {"summary": "...", "suggestion": "..."}'
    )
    user = "DATA:\n" + json.dumps(data, default=str)
    return system, user
