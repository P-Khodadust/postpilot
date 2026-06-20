from __future__ import annotations

from postpilot.entitlements.limits import FREE_PLAN, PLANS_BY_CODE, LimitKey


def test_plan_matrix_monotonic():
    free = PLANS_BY_CODE["free"]
    starter = PLANS_BY_CODE["starter"]
    pro = PLANS_BY_CODE["pro"]
    key = LimitKey.SCHEDULED_POSTS_PER_MONTH
    assert free.limits[key] < starter.limits[key] < pro.limits[key]
    assert free.price_cents == 0 < starter.price_cents < pro.price_cents


def test_every_plan_defines_every_limit_key():
    keys = set(FREE_PLAN.limits)
    for plan in PLANS_BY_CODE.values():
        assert set(plan.limits) == keys, f"{plan.code} missing limit keys"
