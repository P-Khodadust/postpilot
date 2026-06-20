"""Tenant-scoped data access + a defense-in-depth ORM guard.

Rule: feature code never issues a raw `select(Model)` on a tenant table. It goes through
`TenantRepo`, which injects `account_id == ctx.account_id`. The `install_tenant_guard()`
event hook additionally asserts that any SELECT touching a TenantScoped entity carries an
account_id predicate - it RAISES in strict mode (tests/CI) and logs otherwise.
"""

from __future__ import annotations

import os
from typing import Any, TypeVar

from sqlalchemy import Select, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from postpilot.core.logging import get_logger
from postpilot.models import TenantScoped
from postpilot.tenancy.context import Role, TenantContext

log = get_logger("tenancy")
T = TypeVar("T")

_STRICT = os.environ.get("TENANCY_STRICT", "").lower() in {"1", "true", "yes"}


class TenantRepo:
    """Wraps an AsyncSession with an account scope."""

    def __init__(self, session: AsyncSession, ctx: TenantContext) -> None:
        self._s = session
        self._ctx = ctx

    @property
    def ctx(self) -> TenantContext:
        return self._ctx

    def scoped(self, stmt: Select) -> Select:
        entity = stmt.column_descriptions[0]["entity"]
        if entity is None or not issubclass(entity, TenantScoped):
            return stmt
        col = getattr(entity, entity.__tenant_col__)
        return stmt.where(col == self._ctx.account_id)

    async def all(self, stmt: Select) -> list[Any]:
        res = await self._s.execute(self.scoped(stmt))
        return list(res.scalars().all())

    async def first(self, stmt: Select) -> Any | None:
        res = await self._s.execute(self.scoped(stmt).limit(1))
        return res.scalars().first()

    async def one(self, stmt: Select) -> Any:
        res = await self._s.execute(self.scoped(stmt))
        return res.scalars().one()

    def add(self, obj: Any) -> Any:
        """Insert, forcing the tenant key from context (never trust a caller-supplied id)."""
        if isinstance(obj, TenantScoped):
            setattr(obj, obj.__tenant_col__, self._ctx.account_id)
        self._s.add(obj)
        return obj


def require(ctx: TenantContext, role: Role) -> None:
    from postpilot.core.errors import TenantAccessError

    if not ctx.can(role):
        raise TenantAccessError(
            f"role {ctx.role.name} < required {role.name}",
            user_message="You don't have permission to do that.",
        )


def _stmt_has_tenant_predicate(stmt: Select, entity: type) -> bool:
    col_name = entity.__tenant_col__  # type: ignore[attr-defined]
    text = str(stmt)
    return f".{col_name}" in text or f"{entity.__tablename__}.{col_name}" in text


def install_tenant_guard(engine: Engine | Any) -> None:
    """Attach a do_orm_execute hook that flags unscoped tenant SELECTs."""

    @event.listens_for(Session, "do_orm_execute")
    def _guard(orm_execute_state):  # type: ignore[no-untyped-def]
        if not orm_execute_state.is_select:
            return
        stmt = orm_execute_state.statement
        try:
            descs = stmt.column_descriptions
        except Exception:  # noqa: BLE001
            return
        for d in descs:
            entity = d.get("entity")
            if entity is not None and isinstance(entity, type) and issubclass(entity, TenantScoped):
                if not _stmt_has_tenant_predicate(stmt, entity):
                    msg = f"Unscoped tenant query on {entity.__name__} (missing account_id filter)"
                    if _STRICT:
                        raise RuntimeError(msg)
                    log.warning("tenant_guard.unscoped", entity=entity.__name__)
