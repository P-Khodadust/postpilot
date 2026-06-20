"""Provider-agnostic billing interface. App code never imports Stripe/Telegram payment types."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass
from typing import Protocol


class SubStatus(str, enum.Enum):
    NONE = "none"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


@dataclass
class CheckoutResult:
    provider: str
    redirect_url: str | None = None          # Stripe hosted checkout
    telegram_invoice: dict | None = None     # payload for bot.send_invoice
    provider_ref: str | None = None


@dataclass
class WebhookResult:
    provider: str
    event_type: str
    account_id: uuid.UUID | None
    new_status: SubStatus | None
    plan_code: str | None
    provider_event_id: str
    handled: bool


class PaymentProvider(Protocol):
    name: str

    async def create_checkout(
        self, account_id: uuid.UUID, plan_code: str, *, trial_days: int | None, idempotency_key: str
    ) -> CheckoutResult: ...

    async def cancel(self, account_id: uuid.UUID, *, at_period_end: bool = True) -> SubStatus: ...

    async def handle_webhook(self, raw_body: bytes, headers: dict[str, str]) -> WebhookResult: ...

    async def get_subscription_status(self, account_id: uuid.UUID) -> SubStatus: ...
