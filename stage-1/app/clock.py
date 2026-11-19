"""The service clock (§3.4): follows system time until reset, then stands still."""

import threading
from datetime import datetime, timezone


class Clock:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._fixed: datetime | None = None

    def _system_now(self) -> datetime:
        return datetime.now(timezone.utc).replace(microsecond=0)

    def now(self) -> datetime:
        with self._lock:
            if self._fixed is not None:
                return self._fixed
        return self._system_now()

    def set_fixed(self, moment: datetime) -> None:
        """Set the clock unconditionally (reset with the fixture's `now`)."""
        with self._lock:
            self._fixed = moment

    def advance_to(self, moment: datetime) -> bool:
        """Move the clock to `moment`; False and no change if it is earlier than now."""
        with self._lock:
            current = self._fixed if self._fixed is not None else self._system_now()
            if moment < current:
                return False
            self._fixed = moment
            return True
