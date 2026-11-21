"""The service clock (spec §3.4). Every timestamp the service reads comes from here."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.errors import validation_failed

_RFC3339 = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$"
)


def parse_rfc3339(text: str) -> datetime:
    """Parse an RFC 3339 timestamp with an explicit offset; raise 422 otherwise."""
    match = _RFC3339.match(text)
    if match is None:
        raise validation_failed("timestamp must be RFC 3339 with an explicit offset")
    year, month, day, hour, minute, second = (int(part) for part in match.group(1, 2, 3, 4, 5, 6))
    fraction, offset = match.group(7), match.group(8)
    microsecond = int((fraction or ".0")[1:7].ljust(6, "0"))
    if offset in ("Z", "z"):
        tz = timezone.utc
    else:
        sign = -1 if offset[0] == "-" else 1
        off_h, off_m = int(offset[1:3]), int(offset[4:6])
        if off_h > 23 or off_m > 59:
            raise validation_failed("timestamp offset out of range")
        tz = timezone(sign * timedelta(hours=off_h, minutes=off_m))
    try:
        return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=tz)
    except ValueError as exc:
        raise validation_failed(f"timestamp out of range: {exc}") from exc


def format_timestamp(when: datetime) -> str:
    """Render an aware datetime as RFC 3339 with an explicit offset."""
    return when.isoformat()


class Clock:
    """Stands still between clock calls once set; before the first reset it follows system time."""

    def __init__(self) -> None:
        self._fixed: datetime | None = None

    def now(self) -> datetime:
        if self._fixed is None:
            return datetime.now(timezone.utc)
        return self._fixed

    def set(self, when: datetime) -> None:
        """Move the clock forward to `when`; an earlier time is a validation error."""
        if when < self.now():
            raise validation_failed("clock cannot move backwards")
        self._fixed = when

    def reset_to(self, when: datetime) -> None:
        """Set the clock unconditionally (used by reset, which replaces all state)."""
        self._fixed = when
