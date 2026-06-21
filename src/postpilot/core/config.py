"""Typed application settings (12-factor, env-only). Fails fast on missing secrets."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    environment: Literal["development", "staging", "production"] = "development"
    public_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"

    # Datastores
    database_url: str = "postgresql+asyncpg://postpilot:postpilot@localhost:5432/postpilot"
    redis_url: str = "redis://localhost:6379/0"

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_use_webhook: bool = True
    telegram_payments_provider_token: str = ""

    # X / Twitter official API
    x_client_id: str = ""
    x_client_secret: str = ""
    x_redirect_uri: str = "http://localhost:8000/oauth/x/callback"
    x_app_monthly_post_cap: int = 450
    x_scopes: list[str] = Field(
        default_factory=lambda: ["tweet.read", "tweet.write", "users.read", "offline.access"]
    )

    # Token encryption (MultiFernet; newest key first)
    token_enc_keys: str = ""

    # AI
    ai_enabled: bool = True
    anthropic_api_key: str = ""
    ai_monthly_token_budget_default: int = 200_000

    # Billing
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""

    # Admin
    admin_session_secret: str = "dev-insecure-change-me"
    admin_ip_allowlist: str = ""

    # Scheduler
    scheduler_tick_seconds: int = 10
    post_max_lateness_minutes: int = 120

    @field_validator("token_enc_keys")
    @classmethod
    def _keys_present_in_prod(cls, v: str, info) -> str:  # type: ignore[no-untyped-def]
        # In production a real key list is mandatory; in dev we tolerate empty (a dev key is generated).
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def enc_key_list(self) -> list[str]:
        return [k.strip() for k in self.token_enc_keys.split(",") if k.strip()]

    @property
    def admin_allowlist_cidrs(self) -> list[str]:
        return [c.strip() for c in self.admin_ip_allowlist.split(",") if c.strip()]

    def require_for_production(self) -> None:
        """Validate that all secrets needed in production are present; raise otherwise."""
        if not self.is_production:
            return
        missing = [
            name
            for name, val in {
                "TELEGRAM_BOT_TOKEN": self.telegram_bot_token,
                "TELEGRAM_WEBHOOK_SECRET": self.telegram_webhook_secret,
                "X_CLIENT_ID": self.x_client_id,
                "X_CLIENT_SECRET": self.x_client_secret,
                "TOKEN_ENC_KEYS": self.token_enc_keys,
                "ANTHROPIC_API_KEY": self.anthropic_api_key,
                "ADMIN_SESSION_SECRET": self.admin_session_secret,
            }.items()
            if not val or val == "dev-insecure-change-me"
        ]
        if missing:
            raise RuntimeError(f"Missing required production settings: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
