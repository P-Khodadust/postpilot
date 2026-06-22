"""Test config. Generates an ephemeral token-encryption key at runtime so crypto
round-trips work in tests without committing any key material to the repo.
"""

from __future__ import annotations

import os

os.environ.setdefault("TENANCY_STRICT", "1")

if not os.environ.get("TOKEN_ENC_KEYS"):
    from cryptography.fernet import Fernet

    os.environ["TOKEN_ENC_KEYS"] = Fernet.generate_key().decode()
