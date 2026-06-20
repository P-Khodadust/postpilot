"""Typed exception hierarchy. User-facing surfaces map these to safe messages."""

from __future__ import annotations


class AppError(Exception):
    """Base for all expected application errors.

    `user_message` is safe to show to an end user; `message` is for logs.
    """

    code: str = "app_error"
    http_status: int = 400

    def __init__(self, message: str, *, user_message: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.user_message = user_message or "Something went wrong. Please try again."


class ValidationError(AppError):
    code = "validation_error"
    http_status = 422


class NotFoundError(AppError):
    code = "not_found"
    http_status = 404


class AuthError(AppError):
    code = "auth_error"
    http_status = 401


class TenantAccessError(AppError):
    """Raised when a query/action is attempted outside the caller's tenant."""

    code = "tenant_access_error"
    http_status = 403


class EntitlementError(AppError):
    code = "entitlement_error"
    http_status = 403


class QuotaError(EntitlementError):
    """A plan limit was reached. Carries enough context to render an upgrade CTA."""

    code = "quota_exceeded"

    def __init__(self, limit_key: str, limit: int, used: int, plan: str) -> None:
        super().__init__(
            f"quota exceeded: {limit_key} used={used} limit={limit} plan={plan}",
            user_message=(
                f"You've reached your plan's limit for this ({used}/{limit}). "
                "Upgrade to keep going."
            ),
        )
        self.limit_key = limit_key
        self.limit = limit
        self.used = used
        self.plan = plan


class ExternalServiceError(AppError):
    code = "external_service_error"
    http_status = 502


class XApiError(ExternalServiceError):
    code = "x_api_error"

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retryable: bool = False,
        reauth_required: bool = False,
        duplicate: bool = False,
        user_message: str | None = None,
    ) -> None:
        super().__init__(message, user_message=user_message)
        self.status = status
        self.retryable = retryable
        self.reauth_required = reauth_required
        self.duplicate = duplicate


class StripeError(ExternalServiceError):
    code = "stripe_error"


class TelegramError(ExternalServiceError):
    code = "telegram_error"
