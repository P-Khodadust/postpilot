"""initial schema + plan seed

Revision ID: 0001
Revises:
Create Date: 2026-06-21

The initial migration creates the full schema directly from the SQLAlchemy metadata
(single source of truth, no transcription drift) and seeds the plan/limit rows.
Subsequent migrations should use Alembic autogenerate.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from postpilot.entitlements.limits import PLANS
from postpilot.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # gen_random_uuid() is used by raw-SQL inserts (ad-hoc post enqueue).
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    Base.metadata.create_all(bind)

    plans = sa.table(
        "plans",
        sa.column("code", sa.String),
        sa.column("display_name", sa.String),
        sa.column("price_cents", sa.Integer),
        sa.column("trial_days", sa.Integer),
        sa.column("sort", sa.Integer),
    )
    plan_limits = sa.table(
        "plan_limits",
        sa.column("plan_code", sa.String),
        sa.column("limit_key", sa.String),
        sa.column("limit_value", sa.Integer),
    )
    op.bulk_insert(
        plans,
        [
            {"code": p.code, "display_name": p.display_name, "price_cents": p.price_cents,
             "trial_days": p.trial_days, "sort": p.sort}
            for p in PLANS
        ],
    )
    op.bulk_insert(
        plan_limits,
        [
            {"plan_code": p.code, "limit_key": k, "limit_value": v}
            for p in PLANS
            for k, v in p.limits.items()
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
