"""Structured JSON logging with secret redaction and correlation ids."""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar

import structlog

correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

_SECRET_PAT = re.compile(
    r"(auth_token|ct0|access_token|refresh_token|client_secret|api_key|password|bearer)"
    r"[=:]\s*([A-Za-z0-9._\-]+)",
    re.IGNORECASE,
)


def _redact(_logger, _method, event_dict):
    for key, val in list(event_dict.items()):
        if isinstance(val, str):
            event_dict[key] = _SECRET_PAT.sub(r"\1=***", val)
    return event_dict


def _add_correlation(_logger, _method, event_dict):
    cid = correlation_id.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_correlation,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
