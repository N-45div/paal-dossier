"""The service clock (spec §3.4).

Before the first reset the clock follows system time. Reset sets it to the fixture's `now`;
`POST /_test/clock` moves it forward. Once set, it stands still between calls.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta, timezone

from .errors import validation_failed

_RFC3339 = re.compile(
    r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})[Tt]"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?:\.(?P<fraction>\d+))?"
    r"(?P<offset>[Zz]|[+-]\d{2}:\d{2})"
)


def parse_rfc3339(text: str) -> datetime:
    """Parse an RFC 3339 timestamp that carries an explicit offset; anything else is 422."""
    match = _RFC3339.fullmatch(text)
    if match is None:
        raise validation_failed("timestamp must be RFC 3339 with an explicit offset")
    offset_text = match["offset"]
    if offset_text in ("Z", "z"):
        offset = timedelta(0)
    else:
        hours, minutes = int(offset_text[1:3]), int(offset_text[4:6])
        if hours > 23 or minutes > 59:
            raise validation_failed("timestamp offset is out of range")
        sign = 1 if offset_text[0] == "+" else -1
        offset = sign * timedelta(hours=hours, minutes=minutes)
    microsecond = int((match["fraction"] or "")[:6].ljust(6, "0"))
    try:
        return datetime(
            int(match["year"]), int(match["month"]), int(match["day"]),
            int(match["hour"]), int(match["minute"]), int(match["second"]),
            microsecond, tzinfo=timezone(offset),
        )
    except ValueError as exc:
        raise validation_failed("timestamp is not a valid date and time") from exc


class Clock:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._fixed: datetime | None = None

    def now(self) -> datetime:
        with self._lock:
            return self._current()

    def reset_to(self, instant: datetime) -> None:
        """Set the clock unconditionally; used by reset, which may move it backwards."""
        with self._lock:
            self._fixed = instant

    def move_to(self, instant: datetime) -> None:
        """Move the clock forward; an earlier instant is 422 and changes nothing."""
        with self._lock:
            if instant < self._current():
                raise validation_failed("now is earlier than the clock's current time")
            self._fixed = instant

    def _current(self) -> datetime:
        if self._fixed is not None:
            return self._fixed
        return datetime.now(timezone.utc).replace(microsecond=0)
