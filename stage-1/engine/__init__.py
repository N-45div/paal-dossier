"""Research engine for Dossier stage 1.

The only package that talks to providers (through web_router, in-process).
Public contract: run_build(domain, ...) -> BuildResult. Never raises.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .ledger import Ledger

FIELD_NAMES = (
    "legal_name",
    "hq_city",
    "ceo",
    "founded_year",
    "headcount_range",
    "funding_total",
)


@dataclass
class BuildResult:
    ok: bool
    spent: int
    fields: dict = field(default_factory=dict)


def _unknown_fields() -> dict:
    return {name: {"value": None, "citations": []} for name in FIELD_NAMES}


def run_build(
    domain: str,
    *,
    budget: int = 80,
    on_spend: Optional[Callable[[int], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
) -> BuildResult:
    """Research one company by its normalised domain. Blocking; never raises.

    ``on_spend(units)`` is called after every provider call that costs units. ``cancelled``
    is polled between calls. ok is False only when no provider call answered.
    """
    from .build import build

    ledger = Ledger(budget, on_spend)
    try:
        ok, fields = build(domain, ledger, cancelled)
    except Exception:  # last resort: a build must never raise into the service
        return BuildResult(ok=False, spent=ledger.spent, fields=_unknown_fields())
    return BuildResult(ok=ok, spent=ledger.spent, fields=fields)
