"""Entitlements: the single answer to 'may this account do X right now?'"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.core.errors import QuotaError
from postpilot.entitlements.limits import FREE_PLAN, PLANS_BY_CODE, UNLIMITED, LimitKey, PlanDef
from postpilot.metering.service import current_period_usage
from postpilot.models import ConnectedXAccount, PlanLimit, Subscription

LIVE_STATUSES = ("trialing", "active", "past_due")


@dataclass
class Entitlements:
    plan_code: str
    limits: dict[str, int]

    def limit(self, key: str) -> int:
        return self.limits.get(key, 0)


async def resolve_plan(session: AsyncSession, account_id: uuid.UUID) -> str:
    sub = (
        await session.execute(
            select(Subscription).where(
                Subscription.account_id == account_id,
                Subscription.status.in_(LIVE_STATUSES),
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        return FREE_PLAN.code
    # past_due keeps limits during the grace window; expiry handled by the billing worker.
    if sub.status == "past_due" and sub.current_period_end and sub.current_period_end < dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3):
        return FREE_PLAN.code
    return sub.plan_code


async def get_entitlements(session: AsyncSession, account_id: uuid.UUID) -> Entitlements:
    plan_code = await resolve_plan(session, account_id)
    # DB is the runtime source of truth (admin-editable); fall back to code seed.
    rows = (
        await session.execute(select(PlanLimit).where(PlanLimit.plan_code == plan_code))
    ).scalars().all()
    if rows:
        limits = {r.limit_key: r.limit_value for r in rows}
    else:
        seed: PlanDef = PLANS_BY_CODE.get(plan_code, FREE_PLAN)
        limits = dict(seed.limits)
    return Entitlements(plan_code=plan_code, limits=limits)


async def check_quota(
    session: AsyncSession, account_id: uuid.UUID, key: str, *, amount: int = 1
) -> None:
    """Raise QuotaError if this action would exceed a monthly counter limit."""
    ent = await get_entitlements(session, account_id)
    limit = ent.limit(key)
    if limit == UNLIMITED:
        return
    used = await current_period_usage(session, account_id=account_id, limit_key=key)
    if used + amount > limit:
        raise QuotaError(key, limit, used, ent.plan_code)


async def assert_can_connect_x(session: AsyncSession, account_id: uuid.UUID) -> None:
    """Point-in-time cap: number of connected X accounts."""
    ent = await get_entitlements(session, account_id)
    limit = ent.limit(LimitKey.MAX_CONNECTED_ACCOUNTS)
    if limit == UNLIMITED:
        return
    count = (
        await session.execute(
            select(func.count())
            .select_from(ConnectedXAccount)
            .where(
                ConnectedXAccount.account_id == account_id,
                ConnectedXAccount.status != "revoked",
            )
        )
    ).scalar_one()
    if count >= limit:
        raise QuotaError(LimitKey.MAX_CONNECTED_ACCOUNTS, limit, count, ent.plan_code)
