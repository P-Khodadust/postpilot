"""Account A must never read Account B's rows; the guard must fire on unscoped queries."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from postpilot.models import Account, RecurringSchedule
from postpilot.tenancy.context import Role, TenantContext
from postpilot.tenancy.repo import TenantRepo


@pytest.mark.asyncio
async def test_repo_scopes_to_account(sessionmaker):
    async with sessionmaker() as s:
        a = Account(name="A")
        b = Account(name="B")
        s.add_all([a, b])
        await s.flush()
        s.add_all([
            RecurringSchedule(account_id=a.id, x_account_id=a.id, name="A-sched",
                              timezone="UTC", config={}),
            RecurringSchedule(account_id=b.id, x_account_id=b.id, name="B-sched",
                              timezone="UTC", config={}),
        ])
        await s.commit()

        ctx_a = TenantContext(a.id, a.id, Role.owner, tg_user_id=1)
        repo = TenantRepo(s, ctx_a)
        rows = await repo.all(select(RecurringSchedule))
        assert {r.name for r in rows} == {"A-sched"}  # B's row is invisible


@pytest.mark.asyncio
async def test_guard_raises_on_unscoped(sessionmaker):
    from postpilot.tenancy.repo import install_tenant_guard

    install_tenant_guard(None)
    async with sessionmaker() as s:
        with pytest.raises(RuntimeError, match="Unscoped tenant query"):
            await s.execute(select(RecurringSchedule))  # no account_id filter
