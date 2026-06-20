"""Request-scoped tenant context. Established once at a trust boundary, never from user input."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass


class Role(enum.IntEnum):
    viewer = 0
    member = 1
    admin = 2
    owner = 3

    @classmethod
    def from_str(cls, s: str) -> Role:
        return cls[s]


@dataclass(frozen=True)
class TenantContext:
    account_id: uuid.UUID
    membership_id: uuid.UUID
    role: Role
    tg_user_id: int

    def can(self, required: Role) -> bool:
        return self.role >= required
