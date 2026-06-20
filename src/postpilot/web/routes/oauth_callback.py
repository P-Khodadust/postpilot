"""X OAuth callback: verify state, exchange code, store encrypted tokens, push Telegram confirm."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from postpilot.core.db import session_scope
from postpilot.core.logging import get_logger
from postpilot.core.security import CURRENT_KEY_VERSION, decrypt, encrypt
from postpilot.models import AuditLog, ConnectedXAccount, OAuthState
from postpilot.x_api import oauth
from postpilot.x_api.client import HttpXClient

router = APIRouter()
log = get_logger("oauth")

_OK_HTML = "<html><body style='font-family:sans-serif'><h2>✅ Connected</h2><p>You can close this tab and return to Telegram.</p></body></html>"
_ERR_HTML = "<html><body style='font-family:sans-serif'><h2>⚠️ Couldn't connect</h2><p>Please return to Telegram and try again.</p></body></html>"


@router.get("/oauth/x/callback")
async def x_callback(request: Request, code: str | None = None, state: str | None = None):
    if not code or not state:
        return HTMLResponse(_ERR_HTML, status_code=400)

    async with session_scope() as session:
        st = await session.get(OAuthState, state)
        if st is None or st.expires_at < dt.datetime.now(dt.timezone.utc):
            return HTMLResponse(_ERR_HTML, status_code=400)

        verifier = decrypt(st.code_verifier_enc)
        account_id, membership_id = st.account_id, st.membership_id
        await session.delete(st)  # one-time use (CSRF)

        try:
            tokens = await oauth.exchange_code(code, verifier)
            me = await HttpXClient().get_me(tokens.access_token)
        except Exception as e:  # noqa: BLE001
            log.warning("oauth.exchange_failed", error=str(e))
            return HTMLResponse(_ERR_HTML, status_code=400)

        now = dt.datetime.now(dt.timezone.utc)
        await session.execute(
            pg_insert(ConnectedXAccount)
            .values(
                account_id=account_id,
                connected_by_membership_id=membership_id,
                x_user_id=me.id,
                x_handle=me.username,
                access_token_enc=encrypt(tokens.access_token),
                refresh_token_enc=encrypt(tokens.refresh_token) if tokens.refresh_token else None,
                enc_key_version=CURRENT_KEY_VERSION,
                scopes=tokens.scopes,
                access_expires_at=now + dt.timedelta(seconds=tokens.expires_in),
                last_refreshed_at=now,
                status="connected",
            )
            .on_conflict_do_update(
                constraint="ux_xacct",
                set_={
                    "access_token_enc": encrypt(tokens.access_token),
                    "refresh_token_enc": encrypt(tokens.refresh_token)
                    if tokens.refresh_token
                    else None,
                    "x_handle": me.username,
                    "access_expires_at": now + dt.timedelta(seconds=tokens.expires_in),
                    "status": "connected",
                    "last_refreshed_at": now,
                    "last_error": None,
                },
            )
        )
        session.add(
            AuditLog(actor_type="user", actor_id=str(membership_id), account_id=account_id,
                     action="x.connected", target_type="x_account", target_id=me.id)
        )
        # resolve the connecting user's chat id for the proactive push
        tg_id = (
            await session.execute(
                select(ConnectedXAccount.id).where(ConnectedXAccount.account_id == account_id)
            )
        ).first()

    # Proactive Telegram confirmation (outside the txn).
    try:
        from postpilot.models import Membership

        async with session_scope() as s2:
            chat_id = (
                await s2.execute(
                    select(Membership.tg_user_id).where(Membership.id == membership_id)
                )
            ).scalar_one_or_none()
        if chat_id:
            await request.app.state.bot.send_message(
                chat_id,
                f"✅ Connected to @{me.username}\n\nNow set your open/close posts from the menu.",
            )
    except Exception as e:  # noqa: BLE001
        log.warning("oauth.push_failed", error=str(e))

    return HTMLResponse(_OK_HTML)
