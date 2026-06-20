"""Test fakes for external services."""

from __future__ import annotations

from postpilot.core.errors import XApiError
from postpilot.x_api.client import PostedTweet, XUser


class FakeXClient:
    """In-memory X client for tests. Configure failures via the constructor."""

    def __init__(self, *, fail_with: XApiError | None = None, handle: str = "testshop") -> None:
        self.fail_with = fail_with
        self.handle = handle
        self.posted: list[str] = []
        self.deleted: list[str] = []
        self._counter = 0

    async def get_me(self, access_token: str) -> XUser:
        return XUser(id="123456", username=self.handle)

    async def create_tweet(self, access_token: str, text: str) -> PostedTweet:
        if self.fail_with is not None:
            raise self.fail_with
        self._counter += 1
        self.posted.append(text)
        return PostedTweet(id=f"tw_{self._counter}", text=text)

    async def delete_tweet(self, access_token: str, tweet_id: str) -> bool:
        self.deleted.append(tweet_id)
        return True
