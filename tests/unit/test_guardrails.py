from __future__ import annotations

from postpilot.ai import guardrails


def test_clamp_tweet():
    assert guardrails.clamp_tweet("hi") == "hi"
    long = "x" * 400
    out = guardrails.clamp_tweet(long)
    assert len(out) <= guardrails.MAX_TWEET and out.endswith("…")


def test_safe_json_handles_fences():
    assert guardrails.safe_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert guardrails.safe_json("not json") is None
    assert guardrails.safe_json("[1,2,3]") is None  # not a dict


def test_sanitize_variants_strips_hashtags_when_disallowed():
    out = guardrails.sanitize_variants(["Open now #shoplocal", ""], allow_emoji=False)
    assert out == ["Open now shoplocal"]
