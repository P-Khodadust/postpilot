"""Resolve a valid X access token for a connected account, refreshing + rotating as needed."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from postpilot.core.logging import get_logger
from postpilot.core.security import CURRENT_KEY_VERSION, decrypt, encrypt
from postpilot.models import ConnectedXAccount
from postpilot.x_api import oauth

log = get_logger("token_refresh")
_REFRESH_SKEW = dt.timedelta(minutes=5)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def valid_access_token(session: AsyncSession, acct: ConnectedXAccount) -> str:
    """Return a usable access token, refreshing (and persisting the ROTATED refresh token) if near expiry.

    Raises XApiError(reauth_required=True) if the refresh token is invalid.
    """
    if acct.status != "connected":
        from postpilot.core.errors import XApiError

        raise XApiError("account not connected", reauth_required=True)

    if acct.access_expires_at - _REFRESH_SKEW > _now():
        return decrypt(acct.access_token_enc)

    if not acct.refresh_token_enc:
        from postpilot.core.errors import XApiError

        raise XApiError("no refresh token", reauth_required=True)

    refresh_token = decrypt(acct.refresh_token_enc)
    try:
        tokens = await oauth.refresh_tokens(refresh_token)
    except Exception as e:  # noqa: BLE001
        acct.status = "reauth_required"
        acct.last_error = str(e)[:300]
        await session.flush()
        raise

    # Persist rotated tokens atomically (X invalidates the old refresh token).
    acct.access_token_enc = encrypt(tokens.access_token)
    if tokens.refresh_token:
        acct.refresh_token_enc = encrypt(tokens.refresh_token)
    acct.enc_key_version = CURRENT_KEY_VERSION
    acct.access_expires_at = _now() + dt.timedelta(seconds=tokens.expires_in)
    acct.last_refreshed_at = _now()
    acct.last_error = None
    await session.flush()
    return tokens.access_token
