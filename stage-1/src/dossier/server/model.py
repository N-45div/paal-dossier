"""Dossier state records and the value rules shared by builds and imports (spec 4, 8)."""

import threading
from dataclasses import dataclass, field
from datetime import datetime

FIELD_NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")
INTEGER_FIELDS = frozenset({"founded_year", "funding_total"})
HEADCOUNT_RANGES = ("1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+")
CITATION_KEYS = ("url", "excerpt", "provider")


@dataclass
class FieldValue:
    """A field: value None means unknown, and then there are no citations."""

    value: str | int | None = None
    citations: list[dict] = field(default_factory=list)


def unknown_fields() -> dict[str, FieldValue]:
    return {name: FieldValue() for name in FIELD_NAMES}


@dataclass(eq=False)
class Build:
    domain: str
    requested_at: datetime
    generation: int
    cancel: threading.Event = field(default_factory=threading.Event)


@dataclass(eq=False)
class Dossier:
    dossier_id: str
    domain: str
    state: str = "failed"  # outcome of the last completed build: "ready" or "failed"
    fields: dict[str, FieldValue] = field(default_factory=unknown_fields)  # last ready build
    researched_at: datetime | None = None  # last ready build
    spent_units: int = 0
    build: Build | None = None  # set while a build runs


@dataclass(eq=False)
class Claim:
    """An idempotency claim: `done` once the first request succeeded (RL1.5)."""

    body: str
    done: bool = False
    payload: dict | None = None


def valid_value(name: str, value: object) -> bool:
    if value is None:
        return True
    if name in INTEGER_FIELDS:
        return type(value) is int and value >= 0
    if name == "headcount_range":
        return value in HEADCOUNT_RANGES
    return isinstance(value, str) and value.strip() != ""


def clean_citations(raw: object) -> list[dict] | None:
    """Keep only well-formed citations; None when any entry is malformed."""
    if not isinstance(raw, list):
        return None
    cleaned = []
    for item in raw:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in CITATION_KEYS):
            return None
        cleaned.append({k: item[k] for k in CITATION_KEYS})
    return cleaned


def known_field(name: str, value: object, citations: object) -> FieldValue | None:
    """A known field needs a valid value and at least one citation; None otherwise."""
    cleaned = clean_citations(citations)
    if value is None or not valid_value(name, value) or not cleaned:
        return None
    return FieldValue(value, cleaned)
