"""X (Twitter) OAuth 2.0 Authorization Code + PKCE.

Confidential client (client_id + client_secret via HTTP Basic). Scopes minimised to what
features need. Refresh tokens ROTATE on every use - callers MUST persist the new one.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from postpilot.core.config import get_settings
from postpilot.core.errors import XApiError
from postpilot.core.security import generate_pkce_verifier, pkce_challenge, random_url_token

AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"  # noqa: S105 - public endpoint, not a secret
REVOKE_URL = "https://api.twitter.com/2/oauth2/revoke"


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_in: int
    scopes: list[str]
    token_type: str = "bearer"


@dataclass
class StartedFlow:
    authorize_url: str
    state: str
    code_verifier: str


def _basic_auth_header() -> dict[str, str]:
    s = get_settings()
    raw = f"{s.x_client_id}:{s.x_client_secret}".encode()
    return {"Authorization": f"Basic {base64.b64encode(raw).decode()}"}


def start_authorization() -> StartedFlow:
    s = get_settings()
    verifier = generate_pkce_verifier()
    state = random_url_token(32)
    params = {
        "response_type": "code",
        "client_id": s.x_client_id,
        "redirect_uri": s.x_redirect_uri,
        "scope": " ".join(s.x_scopes),
        "state": state,
        "code_challenge": pkce_challenge(verifier),
        "code_challenge_method": "S256",
    }
    return StartedFlow(f"{AUTHORIZE_URL}?{urlencode(params)}", state, verifier)


async def exchange_code(code: str, code_verifier: str) -> TokenSet:
    s = get_settings()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": s.x_redirect_uri,
        "code_verifier": code_verifier,
        "client_id": s.x_client_id,
    }
    return await _token_request(data)


async def refresh_tokens(refresh_token: str) -> TokenSet:
    s = get_settings()
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": s.x_client_id,
    }
    return await _token_request(data)


async def revoke(token: str) -> None:
    s = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            REVOKE_URL,
            data={"token": token, "client_id": s.x_client_id},
            headers={**_basic_auth_header(), "Content-Type": "application/x-www-form-urlencoded"},
        )


async def _token_request(data: dict[str, str]) -> TokenSet:
    headers = {**_basic_auth_header(), "Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(TOKEN_URL, data=data, headers=headers)
    if resp.status_code != 200:
        body = resp.text[:300]
        reauth = "invalid_grant" in body
        raise XApiError(
            f"token request failed ({resp.status_code}): {body}",
            status=resp.status_code,
            reauth_required=reauth,
            user_message="Couldn't connect to X. Please try connecting again.",
        )
    j = resp.json()
    return TokenSet(
        access_token=j["access_token"],
        refresh_token=j.get("refresh_token"),
        expires_in=int(j.get("expires_in", 7200)),
        scopes=j.get("scope", "").split() if j.get("scope") else get_settings().x_scopes,
        token_type=j.get("token_type", "bearer"),
    )
