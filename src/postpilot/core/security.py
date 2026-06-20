"""Token encryption at rest (versioned MultiFernet) + small crypto helpers.

X OAuth access/refresh tokens and PKCE verifiers are encrypted before any DB write.
Keys come from settings (TOKEN_ENC_KEYS, newest first) to support zero-downtime rotation.
In development with no key configured, an ephemeral key is generated so the app boots
(those ciphertexts won't survive a restart - acceptable for dev only).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, MultiFernet

from postpilot.core.config import get_settings


def _build_multifernet() -> tuple[MultiFernet, int]:
    settings = get_settings()
    keys = settings.enc_key_list
    if not keys:
        if settings.is_production:
            raise RuntimeError("TOKEN_ENC_KEYS is required in production")
        keys = [Fernet.generate_key().decode()]
    fernets = [Fernet(k.encode() if isinstance(k, str) else k) for k in keys]
    # enc_key_version = index 0 (newest). Stored alongside ciphertext for rotation tracking.
    return MultiFernet(fernets), 1


_MF, CURRENT_KEY_VERSION = _build_multifernet()


def encrypt(plaintext: str) -> bytes:
    """Encrypt a secret string -> ciphertext bytes (store in BYTEA)."""
    return _MF.encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    """Decrypt ciphertext bytes -> plaintext string. Decrypt only at point of use."""
    return _MF.decrypt(ciphertext).decode("utf-8")


def rotate(ciphertext: bytes) -> bytes:
    """Re-encrypt a value under the newest key (used by the key-rotation sweeper)."""
    return _MF.rotate(ciphertext)


# ---- PKCE helpers (RFC 7636) ----
def generate_pkce_verifier() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def random_url_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def sign(value: str, *, secret: str) -> str:
    """HMAC-sign a value (e.g., OAuth state binding). Returns value.signature."""
    sig = hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{sig}"


def verify_signed(signed: str, *, secret: str) -> str | None:
    """Return the value if the signature is valid, else None (constant-time compare)."""
    try:
        value, sig = signed.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()
    return value if hmac.compare_digest(sig, expected) else None
