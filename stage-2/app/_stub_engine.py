"""Fallback engine used until engine/ lands: every field unknown, nothing spent, ok=True."""

from dataclasses import dataclass, field
from typing import Any

FIELD_NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")


@dataclass
class BuildResult:
    ok: bool
    spent: int
    fields: dict[str, Any] = field(default_factory=dict)


def run_build(domain: str, *, budget: int = 80, on_spend=None, cancelled=None) -> BuildResult:
    unknown = {"value": None, "status": "unknown", "citations": [], "candidates": []}
    return BuildResult(ok=True, spent=0, fields={name: dict(unknown) for name in FIELD_NAMES})
