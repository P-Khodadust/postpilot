from __future__ import annotations

import uuid

from postpilot.tenancy.context import Role, TenantContext


def test_role_ordering():
    assert Role.owner > Role.admin > Role.member > Role.viewer
    assert Role.from_str("owner") is Role.owner


def test_context_can():
    ctx = TenantContext(uuid.uuid4(), uuid.uuid4(), Role.member, tg_user_id=42)
    assert ctx.can(Role.member) is True
    assert ctx.can(Role.viewer) is True
    assert ctx.can(Role.admin) is False
