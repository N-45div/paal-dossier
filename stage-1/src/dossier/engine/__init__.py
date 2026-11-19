"""Build engine for dossiers (RL1.3 contract).

``run_build`` researches one company through WebRouter and returns a ``BuildResult``.
It never raises, never touches the clock, HTTP layer or store, and stops early when
``cancel`` is set.
"""

from __future__ import annotations

import threading

from .build import build_fields
from .result import FIELD_NAMES, BuildResult, FieldResult, unknown_fields

__all__ = [
    "FIELD_NAMES",
    "BuildResult",
    "FieldResult",
    "run_build",
    "unknown_fields",
]

BUDGET_UNITS = 80
DEADLINE_SECONDS = 280


def run_build(domain: str, cancel: threading.Event) -> BuildResult:
    """Research ``domain`` and return what the evidence supports.

    Any internal error yields ``ok=False`` with the units spent so far.
    """
    gateway = None
    try:
        from .gateway import Gateway  # the provider gateway (P4a)

        gateway = Gateway(budget=BUDGET_UNITS, deadline_s=DEADLINE_SECONDS, cancel=cancel)
        return build_fields(domain, gateway)
    except Exception:
        spent = gateway.spent if gateway is not None else 0
        return BuildResult(ok=False, spent_units=spent, fields=unknown_fields())
