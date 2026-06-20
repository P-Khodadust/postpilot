"""Pure message-rotation + schedule-expansion helpers (no I/O - fully unit-testable).

Ported and generalized from the shop_autotweet prototype (pick_message + the config shape).
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass
from zoneinfo import ZoneInfo

Slot = str  # 'open' | 'close'


def next_variant(variants: list[str], cursor: int) -> tuple[str, int]:
    """Return (chosen_text, new_cursor). Rotates so the same line isn't reused back-to-back."""
    if not variants:
        raise ValueError("variants must be non-empty")
    idx = cursor % len(variants)
    return variants[idx], (cursor + 1) % len(variants)


def decorate(text: str, *, append_date: bool, on_day: dt.date) -> str:
    """Optionally append a short date so consecutive posts are never byte-identical (X dup guard)."""
    if not append_date:
        return text
    return f"{text} ({on_day.strftime('%a %b %d')})"


def idempotency_key(schedule_id: str, slot: Slot, fire_at_utc: dt.datetime) -> str:
    raw = f"{schedule_id}|{slot}|{fire_at_utc.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:48]


@dataclass(frozen=True)
class PlannedPost:
    slot: Slot
    fire_at_utc: dt.datetime
    idempotency_key: str


def plan_day(
    config: dict,
    *,
    tz_name: str,
    on_day: dt.date,
    schedule_id: str,
) -> list[PlannedPost]:
    """Expand a schedule's config into concrete UTC fire-times for one tenant-local day.

    config shape (reused): {"schedule": {"0".."6": {"open":"HH:MM","close":"HH:MM"}|null},
                            "messages": {...}, "append_date": bool}
    """
    tz = ZoneInfo(tz_name)
    dow = str(on_day.weekday())  # 0=Mon..6=Sun, matching the prototype
    day_cfg = (config.get("schedule") or {}).get(dow)
    if not day_cfg:
        return []
    planned: list[PlannedPost] = []
    for slot in ("open", "close"):
        hhmm = day_cfg.get(slot)
        if not hhmm:
            continue
        hh, mm = (int(x) for x in hhmm.split(":"))
        local = dt.datetime(on_day.year, on_day.month, on_day.day, hh, mm, tzinfo=tz)
        utc = local.astimezone(dt.timezone.utc)
        planned.append(PlannedPost(slot, utc, idempotency_key(schedule_id, slot, utc)))
    return planned


def is_too_late(fire_at_utc: dt.datetime, now_utc: dt.datetime, max_lateness_minutes: int) -> bool:
    """Catch-up guard: don't fire a stale time-sensitive post after downtime."""
    return (now_utc - fire_at_utc) > dt.timedelta(minutes=max_lateness_minutes)
