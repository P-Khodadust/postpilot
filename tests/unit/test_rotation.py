"""Pure scheduling logic - no DB/Redis."""

from __future__ import annotations

import datetime as dt

import pytest

from postpilot.scheduler import rotation


def test_next_variant_rotates():
    variants = ["a", "b", "c"]
    chosen, c1 = rotation.next_variant(variants, 0)
    assert chosen == "a" and c1 == 1
    chosen, c2 = rotation.next_variant(variants, c1)
    assert chosen == "b" and c2 == 2
    chosen, c3 = rotation.next_variant(variants, 2)
    assert chosen == "c" and c3 == 0  # wraps


def test_next_variant_empty_raises():
    with pytest.raises(ValueError):
        rotation.next_variant([], 0)


def test_decorate_appends_date_only_when_enabled():
    day = dt.date(2026, 6, 21)
    assert rotation.decorate("Open!", append_date=False, on_day=day) == "Open!"
    out = rotation.decorate("Open!", append_date=True, on_day=day)
    assert out.startswith("Open! (") and "2026" not in out  # short date, no year noise


def test_idempotency_key_is_stable_and_distinct():
    t = dt.datetime(2026, 6, 21, 8, 0, tzinfo=dt.timezone.utc)
    k1 = rotation.idempotency_key("sched-1", "open", t)
    k2 = rotation.idempotency_key("sched-1", "open", t)
    k3 = rotation.idempotency_key("sched-1", "close", t)
    assert k1 == k2 and k1 != k3 and len(k1) == 48


def test_plan_day_converts_local_to_utc():
    cfg = {
        "schedule": {"5": {"open": "09:00", "close": "17:00"}},  # 5 = Saturday
        "messages": {"open": ["o"], "close": ["c"]},
        "append_date": True,
    }
    saturday = dt.date(2026, 6, 20)
    planned = rotation.plan_day(cfg, tz_name="UTC", on_day=saturday, schedule_id="s1")
    assert [p.slot for p in planned] == ["open", "close"]
    assert planned[0].fire_at_utc == dt.datetime(2026, 6, 20, 9, 0, tzinfo=dt.timezone.utc)


def test_plan_day_empty_for_closed_day():
    cfg = {"schedule": {"6": None}, "messages": {}, "append_date": False}
    assert rotation.plan_day(cfg, tz_name="UTC", on_day=dt.date(2026, 6, 21), schedule_id="s") == []


def test_is_too_late():
    now = dt.datetime(2026, 6, 21, 12, 0, tzinfo=dt.timezone.utc)
    old = now - dt.timedelta(hours=3)
    fresh = now - dt.timedelta(minutes=5)
    assert rotation.is_too_late(old, now, 120) is True
    assert rotation.is_too_late(fresh, now, 120) is False
