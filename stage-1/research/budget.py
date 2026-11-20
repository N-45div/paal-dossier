"""The unit budget of one build (stage-1.md section 9)."""

import threading

UNIT_CAP = 80
SEARCH_UNITS = 1  # Nimble search, depth lite
EXTRACT_UNITS_PER_URL = 1  # Nimble extract, no render
RESEARCH_UNITS = 25  # Nimble research run, charged when started


class Budget:
    """Units charged so far, never above the cap. A reservation is a charge; a refused call refunds it."""

    def __init__(self, cap: int = UNIT_CAP) -> None:
        self._cap = cap
        self._spent = 0
        self._lock = threading.Lock()

    @property
    def spent(self) -> int:
        with self._lock:
            return self._spent

    def reserve(self, units: int) -> bool:
        with self._lock:
            if self._spent + units > self._cap:
                return False
            self._spent += units
            return True

    def refund(self, units: int) -> None:
        with self._lock:
            self._spent -= units
