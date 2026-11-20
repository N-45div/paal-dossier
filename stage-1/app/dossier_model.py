"""The dossier: six fields, each with its value and citations, and its committed state (§4, §8).

`state` is what callers see. While a build runs it is `building`; otherwise it is the outcome
of the last completed build (`committed_state`). Fields, `researched_at` and `spent_units`
change only when a build completes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from typing import Any

FIELD_NAMES: tuple[str, ...] = (
    "legal_name",
    "hq_city",
    "ceo",
    "founded_year",
    "headcount_range",
    "funding_total",
)
CITATION_KEYS: tuple[str, ...] = ("url", "excerpt", "provider")


def unknown_field() -> dict[str, Any]:
    return {"value": None, "status": "unknown", "citations": []}


def unknown_fields() -> dict[str, dict[str, Any]]:
    return {name: unknown_field() for name in FIELD_NAMES}


def citation_from(raw: Any) -> dict[str, str] | None:
    """The three citation keys of `raw`, or None when it is not a complete citation."""
    if not isinstance(raw, Mapping):
        return None
    if not all(isinstance(raw.get(key), str) for key in CITATION_KEYS):
        return None
    return {key: raw[key] for key in CITATION_KEYS}


def fields_from_outcome(raw: Any) -> dict[str, dict[str, Any]]:
    """Six fields from a build outcome. A field without a value or citation is unknown."""
    fields = unknown_fields()
    if not isinstance(raw, Mapping):
        return fields
    for name in FIELD_NAMES:
        entry = raw.get(name)
        if not isinstance(entry, Mapping) or entry.get("value") is None:
            continue
        citations = [
            citation
            for citation in (citation_from(item) for item in entry.get("citations") or [])
            if citation is not None
        ]
        if citations:
            fields[name] = {"value": entry["value"], "status": "known", "citations": citations}
    return fields


@dataclass
class Dossier:
    dossier_id: str
    domain: str
    building: bool = False
    committed_state: str | None = None  # "ready" or "failed" once a build has completed
    researched_at: datetime | None = None
    spent_units: int = 0
    fields: dict[str, dict[str, Any]] = dataclass_field(default_factory=unknown_fields)

    @property
    def state(self) -> str:
        if self.building:
            return "building"
        return self.committed_state or "failed"

    @property
    def legal_name(self) -> str | None:
        return self.fields["legal_name"]["value"]
