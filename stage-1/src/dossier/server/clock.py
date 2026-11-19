"""The service clock: system time until reset or POST /_test/clock sets it (spec 3.4).

The clock is only read or written while the store lock is held.
"""

from datetime import datetime, timezone


class Clock:
    def __init__(self) -> None:
        self._fixed: datetime | None = None

    def now(self) -> datetime:
        if self._fixed is None:
            return datetime.now(timezone.utc)
        return self._fixed

    def set(self, instant: datetime) -> None:
        self._fixed = instant
