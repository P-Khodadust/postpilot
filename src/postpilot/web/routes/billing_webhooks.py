"""Stripe billing webhook -> normalize -> update subscription (idempotent)."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from postpilot.billing.stripe_provider import StripeProvider
from postpilot.core.db import session_scope
from postpilot.core.errors import StripeError
from postpilot.core.logging import get_logger
from postpilot.models import BillingEvent, Subscription

router = APIRouter()
log = get_logger("billing.webhook")


@router.post("/billing/stripe/webhook")
async def stripe_webhook(request: Request):
    raw = await request.body()
    try:
        result = await StripeProvider().handle_webhook(raw, dict(request.headers))
    except StripeError:
        return {"ok": False}, 400

    async with session_scope() as session:
        # Idempotent: skip if we've already processed this provider event id.
        ins = await session.execute(
            pg_insert(BillingEvent)
            .values(provider=result.provider, provider_event_id=result.provider_event_id,
                    type=result.event_type, payload={}, processed_at=dt.datetime.now(dt.timezone.utc))
            .on_conflict_do_nothing(constraint="ux_billing_event")
            .returning(BillingEvent.id)
        )
        if ins.first() is None:
            return {"ok": True, "dedup": True}

        if result.handled and result.account_id and result.new_status:
            sub = (
                await session.execute(
                    select(Subscription).where(Subscription.account_id == result.account_id)
                )
            ).scalars().first()
            if sub is None:
                sub = Subscription(account_id=result.account_id, plan_code=result.plan_code or "starter",
                                   provider="stripe")
                session.add(sub)
            sub.status = result.new_status.value
            if result.plan_code:
                sub.plan_code = result.plan_code
    return {"ok": True}
