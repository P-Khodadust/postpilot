"""Telegram-native billing (Stars / Telegram Payments). Same interface, in-bot UX."""

from __future__ import annotations

import uuid

from postpilot.billing.base import CheckoutResult, PaymentProvider, SubStatus, WebhookResult
from postpilot.entitlements.limits import PLANS_BY_CODE


class TelegramPaymentsProvider(PaymentProvider):
    name = "telegram"

    async def create_checkout(
        self, account_id: uuid.UUID, plan_code: str, *, trial_days: int | None, idempotency_key: str
    ) -> CheckoutResult:
        plan = PLANS_BY_CODE[plan_code]
        stars = max(1, plan.price_cents // 100)  # rough USD->Stars mapping; tune at launch
        invoice = {
            "title": f"PostPilot {plan.display_name}",
            "description": f"{plan.display_name} plan - monthly",
            "payload": f"{account_id}:{plan_code}:{idempotency_key}",
            "currency": "XTR",  # Telegram Stars
            "prices": [{"label": plan.display_name, "amount": stars}],
        }
        return CheckoutResult(provider=self.name, telegram_invoice=invoice, provider_ref=idempotency_key)

    async def cancel(self, account_id: uuid.UUID, *, at_period_end: bool = True) -> SubStatus:
        return SubStatus.CANCELED if not at_period_end else SubStatus.ACTIVE

    async def handle_webhook(self, raw_body: bytes, headers: dict[str, str]) -> WebhookResult:
        # Telegram payments arrive as bot updates (pre_checkout_query / successful_payment),
        # handled in bot.handlers.billing; this method exists for interface symmetry.
        return WebhookResult(
            provider=self.name, event_type="noop", account_id=None, new_status=None,
            plan_code=None, provider_event_id="", handled=False,
        )

    async def get_subscription_status(self, account_id: uuid.UUID) -> SubStatus:
        return SubStatus.NONE


def get_provider(name: str) -> PaymentProvider:
    from postpilot.billing.stripe_provider import StripeProvider

    return {"stripe": StripeProvider, "telegram": TelegramPaymentsProvider}.get(
        name, StripeProvider
    )()
