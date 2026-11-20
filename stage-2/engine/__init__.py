"""Research engine for Dossier stage 1.

The only package that talks to providers (through web_router, in-process).
Public contract: run_build(domain, ...) -> BuildResult. Never raises.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from .ledger import Ledger
from .support import FIELDS

FIELD_NAMES = FIELDS


@dataclass
class BuildResult:
    ok: bool
    spent: int
    fields: dict = field(default_factory=dict)


def utc_now_rfc3339() -> str:
    """The default clock: the current UTC time, RFC 3339 with an explicit offset."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _unknown_fields() -> dict:
    return {
        name: {"value": None, "status": "unknown", "citations": [], "candidates": []}
        for name in FIELD_NAMES
    }


def run_build(
    domain: str,
    *,
    budget: int = 80,
    on_spend: Optional[Callable[[int], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
    clock: Callable[[], str] = utc_now_rfc3339,
) -> BuildResult:
    """Research one company by its normalised domain. Blocking; never raises.

    ``on_spend(units)`` is called after every provider call that costs units. ``cancelled``
    is polled between calls. ``clock`` returns the build's RFC 3339 time, stamped as
    retrieved_at on every candidate. ok is False only when no provider call answered.
    """
    from .build import build

    ledger = Ledger(budget, on_spend)
    try:
        ok, fields = build(domain, ledger, clock(), cancelled)
    except Exception:  # last resort: a build must never raise into the service
        return BuildResult(ok=False, spent=ledger.spent, fields=_unknown_fields())
    return BuildResult(ok=ok, spent=ledger.spent, fields=fields)
