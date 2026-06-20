"""Test config. Sets a stable token-encryption key so crypto round-trips are deterministic."""

from __future__ import annotations

import os

os.environ.setdefault(
    "TOKEN_ENC_KEYS", "V6k4suSthR42J6nIJoFepp8kIp_GMjEpdkLCYLSNzME="  # dev-only Fernet key
)
os.environ.setdefault("TENANCY_STRICT", "1")
