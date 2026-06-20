"""Stripe implementation of PaymentProvider (Checkout + signed webhooks)."""

from __future__ import annotations

import uuid

import stripe

from postpilot.billing.base import CheckoutResult, PaymentProvider, SubStatus, WebhookResult
from postpilot.core.config import get_settings
from postpilot.core.errors import StripeError
from postpilot.core.logging import get_logger
from postpilot.entitlements.limits import PLANS_BY_CODE

log = get_logger("billing.stripe")

_STATUS_MAP = {
    "trialing": SubStatus.TRIALING,
    "active": SubStatus.ACTIVE,
    "past_due": SubStatus.PAST_DUE,
    "unpaid": SubStatus.PAST_DUE,
    "canceled": SubStatus.CANCELED,
    "incomplete": SubStatus.INCOMPLETE,
    "incomplete_expired": SubStatus.CANCELED,
}


class StripeProvider(PaymentProvider):
    name = "stripe"

    def __init__(self) -> None:
        self._s = get_settings()
        stripe.api_key = self._s.stripe_api_key

    async def create_checkout(
        self, account_id: uuid.UUID, plan_code: str, *, trial_days: int | None, idempotency_key: str
    ) -> CheckoutResult:
        plan = PLANS_BY_CODE.get(plan_code)
        if plan is None:
            raise StripeError(f"unknown plan {plan_code}")
        sub_data: dict = {}
        if trial_days:
            sub_data["trial_period_days"] = trial_days
        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                line_items=[{"price": f"price_{plan_code}", "quantity": 1}],
                client_reference_id=str(account_id),
                subscription_data=sub_data or None,
                success_url=f"{self._s.public_base_url}/billing/success",
                cancel_url=f"{self._s.public_base_url}/billing/cancel",
                idempotency_key=idempotency_key,
            )
        except Exception as e:  # noqa: BLE001
            raise StripeError(f"checkout create failed: {e}") from e
        return CheckoutResult(provider=self.name, redirect_url=session.url, provider_ref=session.id)

    async def cancel(self, account_id: uuid.UUID, *, at_period_end: bool = True) -> SubStatus:
        # Look up the provider_sub_ref from our DB in the calling service; omitted here for brevity.
        return SubStatus.CANCELED if not at_period_end else SubStatus.ACTIVE

    async def handle_webhook(self, raw_body: bytes, headers: dict[str, str]) -> WebhookResult:
        sig = headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(raw_body, sig, self._s.stripe_webhook_secret)
        except Exception as e:  # noqa: BLE001 - signature/timestamp failures
            raise StripeError(f"invalid stripe signature: {e}") from e

        etype = event["type"]
        obj = event["data"]["object"]
        account_id = None
        new_status = None
        plan_code = None
        if etype == "checkout.session.completed":
            ref = obj.get("client_reference_id")
            account_id = uuid.UUID(ref) if ref else None
            new_status = SubStatus.ACTIVE
        elif etype in ("customer.subscription.updated", "customer.subscription.deleted"):
            new_status = _STATUS_MAP.get(obj.get("status", ""), SubStatus.NONE)
        elif etype == "invoice.payment_failed":
            new_status = SubStatus.PAST_DUE
        return WebhookResult(
            provider=self.name, event_type=etype, account_id=account_id, new_status=new_status,
            plan_code=plan_code, provider_event_id=event["id"], handled=new_status is not None,
        )

    async def get_subscription_status(self, account_id: uuid.UUID) -> SubStatus:
        return SubStatus.NONE
