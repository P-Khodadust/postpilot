"""Map a Telegram user to an Account + Membership and build the TenantContext."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.models import Account, Membership, TgUser
from postpilot.tenancy.context import Role, TenantContext


async def get_or_create_context(
    session: AsyncSession, *, tg_user_id: int, username: str | None
) -> TenantContext:
    """Idempotently provision a personal account on first contact; return tenant context."""
    tg = await session.get(TgUser, tg_user_id)
    if tg is None:
        tg = TgUser(id=tg_user_id, username=username)
        session.add(tg)
        await session.flush()
    elif username and tg.username != username:
        tg.username = username

    membership = (
        await session.execute(
            select(Membership).where(Membership.tg_user_id == tg_user_id).limit(1)
        )
    ).scalar_one_or_none()

    if membership is None:
        account = Account(name=f"{username or 'My'} business")
        session.add(account)
        await session.flush()
        membership = Membership(account_id=account.id, tg_user_id=tg_user_id, role="owner")
        session.add(membership)
        await session.flush()

    return TenantContext(
        account_id=membership.account_id,
        membership_id=membership.id,
        role=Role.from_str(membership.role),
        tg_user_id=tg_user_id,
    )


async def is_onboarded(session: AsyncSession, account_id) -> bool:
    from postpilot.models import ConnectedXAccount

    row = (
        await session.execute(
            select(ConnectedXAccount.id)
            .where(ConnectedXAccount.account_id == account_id,
                   ConnectedXAccount.status == "connected")
            .limit(1)
        )
    ).scalar_one_or_none()
    return row is not None
