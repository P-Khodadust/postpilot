from __future__ import annotations

from postpilot.core import security


def test_token_encrypt_round_trip():
    secret = "x-access-token-abc123"
    ct = security.encrypt(secret)
    assert ct != secret.encode()
    assert security.decrypt(ct) == secret


def test_pkce_challenge_is_deterministic():
    v = security.generate_pkce_verifier()
    assert security.pkce_challenge(v) == security.pkce_challenge(v)
    assert "=" not in security.pkce_challenge(v)  # base64url, no padding


def test_signed_value_round_trip_and_tamper():
    signed = security.sign("account-1", secret="s3cr3t")
    assert security.verify_signed(signed, secret="s3cr3t") == "account-1"
    assert security.verify_signed(signed, secret="wrong") is None
    assert security.verify_signed(signed + "x", secret="s3cr3t") is None
