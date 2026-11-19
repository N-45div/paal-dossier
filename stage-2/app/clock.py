"""The service clock: moved only by reset and POST /_test/clock (§3.4)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_RFC3339 = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|[+-]\d{2}:\d{2})"
)


def parse_rfc3339(text: str) -> datetime:
    """Parse an RFC 3339 timestamp with an explicit offset; ValueError otherwise."""
    match = _RFC3339.fullmatch(text)
    if match is None:
        raise ValueError("not an RFC 3339 timestamp with an offset")
    year, month, day, hour, minute, second, fraction, offset = match.groups()
    micro = int((fraction[1:] + "000000")[:6]) if fraction else 0
    offset_text = "+00:00" if offset in ("Z", "z") else offset
    sign = -1 if offset_text[0] == "-" else 1
    offset_minutes = int(offset_text[1:3]) * 60 + int(offset_text[4:6])
    if offset_minutes >= 24 * 60 or int(offset_text[4:6]) > 59:
        raise ValueError("invalid offset")
    zone = timezone(sign * timedelta(minutes=offset_minutes))
    return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), micro, zone)


class Clock:
    """Follows system time until first set, then stands still."""

    def __init__(self) -> None:
        self._fixed: datetime | None = None

    def now(self) -> datetime:
        if self._fixed is not None:
            return self._fixed
        return datetime.now(timezone.utc).replace(microsecond=0)

    def set(self, moment: datetime) -> None:
        self._fixed = moment

    def now_text(self) -> str:
        return self.now().isoformat()
