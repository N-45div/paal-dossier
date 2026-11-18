"""Company research: turns a domain into six dossier fields with citations.

The only entry point is :func:`run_build`.
"""
from __future__ import annotations

from typing import Callable

FIELD_NAMES = (
    "legal_name",
    "hq_city",
    "ceo",
    "founded_year",
    "headcount_range",
    "funding_total",
)


def unknown_fields() -> dict:
    return {
        name: {"value": None, "status": "unknown", "citations": []}
        for name in FIELD_NAMES
    }


async def run_build(domain: str, spend: Callable[[int], None]) -> dict:
    """Research ``domain`` (already normalised).

    ``spend(units)`` is called once per provider call with its cost.
    Returns ``{"ok": bool, "fields": {...six fields...}}``; ``ok`` is false
    exactly when no provider call of the build succeeded.
    """
    from .build import run_build as _run

    return await _run(domain, spend)
