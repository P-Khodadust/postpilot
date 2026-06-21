"""SQLAlchemy 2.0 models. Shared-schema multi-tenancy keyed by account_id.

Tenant-scoped tables inherit `TenantScoped` (declares `account_id` + `__tenant_col__`),
which the tenancy guard (see postpilot.tenancy.repo) uses to enforce isolation.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from postpilot.core.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TenantScoped:
    """Marker for tenant-owned tables. `account_id` is the isolation key."""

    __tenant_col__ = "account_id"


# --------------------------------------------------------------------------- #
# Identity & tenancy
# --------------------------------------------------------------------------- #
class Account(Base, TimestampMixin):
    __tablename__ = "accounts"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False, default="My business")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    trial_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    __table_args__ = (
        CheckConstraint("status in ('active','past_due','suspended','closed')", name="ck_account_status"),
    )


class TgUser(Base):
    __tablename__ = "tg_users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user id
    username: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Membership(Base, TimestampMixin, TenantScoped):
    __tablename__ = "memberships"
    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    tg_user_id: Mapped[int] = mapped_column(
        ForeignKey("tg_users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="owner")
    __table_args__ = (
        UniqueConstraint("account_id", "tg_user_id", name="ux_membership"),
        Index("ix_membership_tg_user", "tg_user_id"),
        CheckConstraint("role in ('owner','admin','member','viewer')", name="ck_membership_role"),
    )


# --------------------------------------------------------------------------- #
# Connected X accounts (encrypted OAuth tokens)
# --------------------------------------------------------------------------- #
class ConnectedXAccount(Base, TimestampMixin, TenantScoped):
    __tablename__ = "connected_x_accounts"
    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    connected_by_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="SET NULL")
    )
    x_user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    x_handle: Mapped[str | None] = mapped_column(String(64))
    access_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    enc_key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    access_expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_refreshed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="connected")
    last_error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("account_id", "x_user_id", name="ux_xacct"),
        Index("ix_xacct_account", "account_id"),
        Index("ix_xacct_refresh_due", "access_expires_at",
              postgresql_where="status = 'connected'"),
        CheckConstraint("status in ('connected','reauth_required','revoked','error')",
                        name="ck_xacct_status"),
    )


class OAuthState(Base):
    __tablename__ = "oauth_states"
    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False
    )
    code_verifier_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_oauth_states_expiry", "expires_at"),)


# --------------------------------------------------------------------------- #
# Scheduling
# --------------------------------------------------------------------------- #
class RecurringSchedule(Base, TimestampMixin, TenantScoped):
    __tablename__ = "recurring_schedules"
    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    x_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connected_x_accounts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, default="Open/Close")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)  # reused shop_autotweet shape
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_materialized_for: Mapped[dt.date | None] = mapped_column(Date)
    variants: Mapped[list[MessageVariant]] = relationship(
        cascade="all, delete-orphan", back_populates="schedule"
    )
    __table_args__ = (
        Index("ix_sched_account", "account_id"),
        Index("ix_sched_active", "is_active", postgresql_where="is_active"),
    )


class MessageVariant(Base, TenantScoped):
    __tablename__ = "message_variants"
    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recurring_schedules.id", ondelete="CASCADE"), nullable=False
    )
    slot: Mapped[str] = mapped_column(String(16), nullable=False)
    variants: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    cursor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schedule: Mapped[RecurringSchedule] = relationship(back_populates="variants")
    __table_args__ = (
        UniqueConstraint("schedule_id", "slot", name="ux_variant_slot"),
        CheckConstraint("slot in ('open','close','custom')", name="ck_variant_slot"),
    )


class PostQueue(Base, TimestampMixin, TenantScoped):
    __tablename__ = "post_queue"
    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    x_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connected_x_accounts.id", ondelete="CASCADE"), nullable=False
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recurring_schedules.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_for: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    leased_by: Mapped[str | None] = mapped_column(String(64))
    leased_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_attempt_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("account_id", "idempotency_key", name="ux_queue_idem"),
        Index("ix_queue_due", "scheduled_for",
              postgresql_where="status in ('pending','failed')"),
        Index("ix_queue_lease_reclaim", "lease_expires_at",
              postgresql_where="status in ('leased','sending')"),
        Index("ix_queue_tenant", "account_id", "status"),
        CheckConstraint(
            "status in ('pending','leased','sending','succeeded','failed','cancelled','skipped','dead')",
            name="ck_queue_status",
        ),
        CheckConstraint("char_length(body) <= 4000", name="ck_queue_body_len"),
    )


class PostHistory(Base, TenantScoped):
    __tablename__ = "post_history"
    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    queue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("post_queue.id", ondelete="SET NULL")
    )
    x_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connected_x_accounts.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    x_tweet_id: Mapped[str | None] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_detail: Mapped[str | None] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    posted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("ix_history_tenant_time", "account_id", "created_at"),
        Index("ux_history_tweet", "x_tweet_id", unique=True,
              postgresql_where="x_tweet_id is not null"),
        CheckConstraint("status in ('succeeded','failed','deleted')", name="ck_history_status"),
    )


# --------------------------------------------------------------------------- #
# Billing
# --------------------------------------------------------------------------- #
class Plan(Base):
    __tablename__ = "plans"
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="usd")
    interval: Mapped[str] = mapped_column(String(8), nullable=False, server_default="month")
    stripe_price_id: Mapped[str | None] = mapped_column(Text)
    telegram_stars: Mapped[int | None] = mapped_column(Integer)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class PlanLimit(Base):
    __tablename__ = "plan_limits"
    plan_code: Mapped[str] = mapped_column(
        ForeignKey("plans.code", ondelete="CASCADE"), primary_key=True
    )
    limit_key: Mapped[str] = mapped_column(String(48), primary_key=True)
    limit_value: Mapped[int] = mapped_column(Integer, nullable=False)  # -1 = unlimited


class Subscription(Base, TimestampMixin, TenantScoped):
    __tablename__ = "subscriptions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"), nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    provider_customer_ref: Mapped[str | None] = mapped_column(Text)
    provider_sub_ref: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    trial_ends_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (
        Index("ux_sub_live_per_account", "account_id", unique=True,
              postgresql_where="status in ('trialing','active','past_due')"),
        Index("ix_sub_provider", "provider", "provider_sub_ref"),
        CheckConstraint("provider in ('stripe','telegram','manual')", name="ck_sub_provider"),
        CheckConstraint(
            "status in ('trialing','active','past_due','canceled','incomplete')",
            name="ck_sub_status",
        ),
    )


class BillingEvent(Base):
    __tablename__ = "billing_events"
    id: Mapped[uuid.UUID] = _uuid_pk()
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("provider", "provider_event_id", name="ux_billing_event"),)


# --------------------------------------------------------------------------- #
# Metering / analytics
# --------------------------------------------------------------------------- #
class UsageCounter(Base, TenantScoped):
    __tablename__ = "usage_counters"
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    period_start: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    limit_key: Mapped[str] = mapped_column(String(48), primary_key=True)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UsageEvent(Base):
    __tablename__ = "usage_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        Index("ix_usage_events_account", "account_id", "occurred_at"),
        Index("ix_usage_events_type", "event_type", "occurred_at"),
    )


class PlatformDailyMetric(Base):
    __tablename__ = "platform_daily_metrics"
    day: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    dau: Mapped[int] = mapped_column(Integer, default=0)
    mau: Mapped[int] = mapped_column(Integer, default=0)
    new_accounts: Mapped[int] = mapped_column(Integer, default=0)
    posts_sent: Mapped[int] = mapped_column(Integer, default=0)
    posts_failed: Mapped[int] = mapped_column(Integer, default=0)
    active_subs: Mapped[int] = mapped_column(Integer, default=0)
    trials: Mapped[int] = mapped_column(Integer, default=0)
    mrr_cents: Mapped[int] = mapped_column(Integer, default=0)


# --------------------------------------------------------------------------- #
# Ops: audit, notifications, admins
# --------------------------------------------------------------------------- #
class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    actor_id: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(48))
    target_id: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    ip: Mapped[str | None] = mapped_column(INET)
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_audit_tenant_time", "account_id", "created_at"),)


class Notification(Base, TenantScoped):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    tg_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("ix_notif_pending", "status", postgresql_where="status = 'pending'"),
    )


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"
    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="readonly")
    totp_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("role in ('superadmin','support','readonly')", name="ck_admin_role"),
    )


__all__ = [
    "Base", "TenantScoped", "TimestampMixin",
    "Account", "TgUser", "Membership", "ConnectedXAccount", "OAuthState",
    "RecurringSchedule", "MessageVariant", "PostQueue", "PostHistory",
    "Plan", "PlanLimit", "Subscription", "BillingEvent",
    "UsageCounter", "UsageEvent", "PlatformDailyMetric",
    "AuditLog", "Notification", "AdminUser",
]
