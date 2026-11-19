"""Start-to-healthy time under --cpus 2 --memory 3g (R1.13, M1.3)."""
from __future__ import annotations

from . import stack

LIMIT_SECONDS = 60.0


def measure(runs: int = 3) -> list[float]:
    """First run is cold (just after the build), later runs are warm."""
    times = []
    for _ in range(runs):
        stack.stop_service()
        times.append(stack.start_service())
    stack.stop_service()
    return times
