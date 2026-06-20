"""Minimal i18n catalog. Keys only (no inline sentences) so translations drop in cleanly.

EN ships now; the structure (catalog dict per locale + named interpolation) is ES/PT/AR-ready.
"""

from __future__ import annotations

EN: dict[str, str] = {
    "welcome": (
        "👋 Welcome to PostPilot\n\n"
        "I keep your X account active automatically - post \"We're open!\", \"Closed for the day\", "
        "and anything else you want, on a schedule.\n\nTakes about 2 minutes. Ready?"
    ),
    "value_prop": (
        "Here's what I'll do for you:\n\n"
        "🌓  Auto-post when you open and close\n"
        "🔁  Rotate wording so X never sees duplicates\n"
        "🗓  Post anything else on a schedule\n"
        "📊  Tell you the best times to post\n\n"
        "First, connect your X account. Nothing posts until you say so."
    ),
    "connect_x": (
        "🔗 Connect your X account\n\n"
        "Tap the button below. X opens in your browser and asks you to allow PostPilot to post "
        "for you. Approve it and come back - I'll confirm automatically.\n\n"
        "🔒 I never see your X password. Disconnect anytime."
    ),
    "connected_ok": "✅ Connected to @{handle}\n\nNice - your X account is linked.",
    "menu": "🏠 PostPilot{conn}\nWhat would you like to do?",
    "help": (
        "PostPilot posts to X for you on a schedule.\n\n"
        "• /connect - link or reconnect your X account\n"
        "• /schedule - set your open/close posts\n"
        "• /post - schedule a one-off post\n"
        "• /posts - see upcoming & past posts\n"
        "• /insights - best times & weekly summary\n"
        "• /billing - your plan\n"
        "• /settings - timezone, language, notifications\n"
        "• /support - talk to us"
    ),
    "not_connected": " - ⚠️ Not connected",
    "quota_posts": "You've used {used}/{limit} scheduled posts this month on {plan}. Upgrade for more.",
}


def t(key: str, locale: str = "en", **kw) -> str:
    text = EN.get(key, key)
    return text.format(**kw) if kw else text
