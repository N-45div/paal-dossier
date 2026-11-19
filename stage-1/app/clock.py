"""The service clock (§3.4): follows system time until reset, then stands still."""

import threading
import time
from datetime import timedelta

from .wire import Moment


class Clock:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._fixed: Moment | None = None

    @staticmethod
    def _system_now() -> Moment:
        return Moment(time.time_ns(), timedelta(0))

    def now(self) -> Moment:
        with self._lock:
            if self._fixed is not None:
                return self._fixed
        return self._system_now()

    def set_fixed(self, moment: Moment) -> None:
        """Set the clock unconditionally (reset with the fixture's `now`)."""
        with self._lock:
            self._fixed = moment

    def advance_to(self, moment: Moment) -> bool:
        """Move the clock to `moment`; False and no change if it is earlier than now."""
        with self._lock:
            current = self._fixed if self._fixed is not None else self._system_now()
            if moment.ns < current.ns:
                return False
            self._fixed = moment
            return True
