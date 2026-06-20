"""X API v2 client (tweets + user lookup). Bearer = a user's OAuth access token.

Retry/backoff/429 handling ported from the last30days http layer:
- retry transient (network, 5xx) with exponential backoff
- on 429 honor Retry-After then bounded backoff
- never retry 4xx (except 429); surface reauth on 401
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

import httpx

from postpilot.core.errors import XApiError
from postpilot.core.logging import get_logger

log = get_logger("x_api")
API_BASE = "https://api.twitter.com/2"
MAX_RETRIES = 4
MAX_429_RETRIES = 2
BASE_BACKOFF = 2.0


@dataclass
class PostedTweet:
    id: str
    text: str


@dataclass
class XUser:
    id: str
    username: str


class XClient(Protocol):
    async def get_me(self, access_token: str) -> XUser: ...
    async def create_tweet(self, access_token: str, text: str) -> PostedTweet: ...
    async def delete_tweet(self, access_token: str, tweet_id: str) -> bool: ...


class HttpXClient:
    """Real client against api.twitter.com."""

    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def _headers(self, access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, access_token: str, **kw) -> httpx.Response:
        url = f"{API_BASE}{path}"
        attempt = 0
        rl_attempt = 0
        async with httpx.AsyncClient(timeout=self._timeout, http2=True) as client:
            while True:
                try:
                    resp = await client.request(method, url, headers=self._headers(access_token), **kw)
                except (httpx.TransportError, httpx.TimeoutException) as e:
                    if attempt >= MAX_RETRIES:
                        raise XApiError(f"network error: {e}", retryable=True) from e
                    await asyncio.sleep(BASE_BACKOFF * (2**attempt))
                    attempt += 1
                    continue

                if resp.status_code == 429:
                    if rl_attempt >= MAX_429_RETRIES:
                        raise XApiError("rate limited", status=429, retryable=True)
                    delay = float(resp.headers.get("retry-after", BASE_BACKOFF * (2**rl_attempt)))
                    log.warning("x_api.429", path=path, delay=delay)
                    await asyncio.sleep(delay)
                    rl_attempt += 1
                    continue

                if 500 <= resp.status_code < 600:
                    if attempt >= MAX_RETRIES:
                        raise XApiError(f"server error {resp.status_code}", status=resp.status_code,
                                        retryable=True)
                    await asyncio.sleep(BASE_BACKOFF * (2**attempt))
                    attempt += 1
                    continue

                return resp

    async def get_me(self, access_token: str) -> XUser:
        resp = await self._request("GET", "/users/me", access_token)
        if resp.status_code == 401:
            raise XApiError("unauthorized", status=401, reauth_required=True)
        if resp.status_code != 200:
            raise XApiError(f"get_me failed {resp.status_code}: {resp.text[:200]}",
                            status=resp.status_code)
        d = resp.json()["data"]
        return XUser(id=d["id"], username=d["username"])

    async def create_tweet(self, access_token: str, text: str) -> PostedTweet:
        resp = await self._request("POST", "/tweets", access_token, json={"text": text})
        if resp.status_code == 401:
            raise XApiError("unauthorized", status=401, reauth_required=True,
                            user_message="Your X connection expired. Please reconnect.")
        if resp.status_code == 403:
            raise XApiError(f"forbidden: {resp.text[:200]}", status=403,
                            user_message="X declined this post (account may be restricted).")
        if resp.status_code in (200, 201):
            d = resp.json()["data"]
            return PostedTweet(id=d["id"], text=d.get("text", text))
        body = resp.text[:300]
        if "duplicate" in body.lower():
            raise XApiError("duplicate content", status=resp.status_code, duplicate=True,
                            user_message="That was identical to a recent post.")
        raise XApiError(f"create_tweet failed {resp.status_code}: {body}", status=resp.status_code)

    async def delete_tweet(self, access_token: str, tweet_id: str) -> bool:
        resp = await self._request("DELETE", f"/tweets/{tweet_id}", access_token)
        if resp.status_code == 200:
            return bool(resp.json().get("data", {}).get("deleted", False))
        return False
