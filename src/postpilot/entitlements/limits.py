"""Plan + limit definitions (limits-as-data). Code is the seed; DB is the runtime source of truth."""

from __future__ import annotations

from dataclasses import dataclass


class LimitKey:
    MAX_CONNECTED_ACCOUNTS = "max_connected_accounts"
    SCHEDULED_POSTS_PER_MONTH = "scheduled_posts_per_month"
    AI_INSIGHT_CALLS_PER_MONTH = "ai_insight_calls_per_month"
    MESSAGE_VARIANTS_PER_POST = "message_variants_per_post"
    SUPPORT_LEVEL = "support_level"  # 0 community, 1 email, 2 priority


UNLIMITED = -1


@dataclass(frozen=True)
class PlanDef:
    code: str
    display_name: str
    price_cents: int
    trial_days: int
    sort: int
    limits: dict[str, int]


PLANS: list[PlanDef] = [
    PlanDef(
        code="free",
        display_name="Free",
        price_cents=0,
        trial_days=0,
        sort=0,
        limits={
            LimitKey.MAX_CONNECTED_ACCOUNTS: 1,
            LimitKey.SCHEDULED_POSTS_PER_MONTH: 15,
            LimitKey.AI_INSIGHT_CALLS_PER_MONTH: 5,
            LimitKey.MESSAGE_VARIANTS_PER_POST: 1,
            LimitKey.SUPPORT_LEVEL: 0,
        },
    ),
    PlanDef(
        code="starter",
        display_name="Starter",
        price_cents=900,
        trial_days=7,
        sort=1,
        limits={
            LimitKey.MAX_CONNECTED_ACCOUNTS: 2,
            LimitKey.SCHEDULED_POSTS_PER_MONTH: 300,
            LimitKey.AI_INSIGHT_CALLS_PER_MONTH: 150,
            LimitKey.MESSAGE_VARIANTS_PER_POST: 3,
            LimitKey.SUPPORT_LEVEL: 1,
        },
    ),
    PlanDef(
        code="pro",
        display_name="Pro",
        price_cents=2900,
        trial_days=7,
        sort=2,
        limits={
            LimitKey.MAX_CONNECTED_ACCOUNTS: 10,
            LimitKey.SCHEDULED_POSTS_PER_MONTH: 3000,
            LimitKey.AI_INSIGHT_CALLS_PER_MONTH: 2000,
            LimitKey.MESSAGE_VARIANTS_PER_POST: 5,
            LimitKey.SUPPORT_LEVEL: 2,
        },
    ),
]

PLANS_BY_CODE = {p.code: p for p in PLANS}
FREE_PLAN = PLANS_BY_CODE["free"]
