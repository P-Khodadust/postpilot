"""Seed the plans + plan_limits tables from the code definitions (idempotent)."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.entitlements.limits import PLANS
from postpilot.models import Plan, PlanLimit


async def seed_plans(session: AsyncSession) -> None:
    for p in PLANS:
        await session.execute(
            pg_insert(Plan)
            .values(
                code=p.code, display_name=p.display_name, price_cents=p.price_cents,
                trial_days=p.trial_days, sort=p.sort,
            )
            .on_conflict_do_update(
                index_elements=[Plan.code],
                set_={"display_name": p.display_name, "price_cents": p.price_cents,
                      "trial_days": p.trial_days, "sort": p.sort},
            )
        )
        for key, val in p.limits.items():
            await session.execute(
                pg_insert(PlanLimit)
                .values(plan_code=p.code, limit_key=key, limit_value=val)
                .on_conflict_do_update(
                    index_elements=[PlanLimit.plan_code, PlanLimit.limit_key],
                    set_={"limit_value": val},
                )
            )
