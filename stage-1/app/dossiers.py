"""Dossier model and its API/export representations (§4, §8)."""
from dataclasses import dataclass, field
from datetime import datetime

from app.clock import render

FIELD_NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range",
               "funding_total")


def unknown_field() -> dict:
    return {"value": None, "status": "unknown", "citations": []}


def unknown_fields() -> dict:
    return {name: unknown_field() for name in FIELD_NAMES}


def clean_field(raw: object) -> dict:
    """A field in the API shape; anything without a value and a citation is unknown."""
    if not isinstance(raw, dict) or raw.get("value") is None:
        return unknown_field()
    citations = [{"url": c["url"], "excerpt": c["excerpt"], "provider": c["provider"]}
                 for c in raw.get("citations") or []]
    if not citations:
        return unknown_field()
    return {"value": raw["value"], "status": "known", "citations": citations}


def clean_fields(raw: object) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    return {name: clean_field(raw.get(name)) for name in FIELD_NAMES}


@dataclass
class Dossier:
    dossier_id: str
    domain: str
    fields: dict = field(default_factory=unknown_fields)
    researched_at: datetime | None = None
    spent_units: int = 0
    committed_spent: int = 0        # spend of every build before the running one
    outcome: str | None = None      # outcome of the last completed build
    building: bool = False

    @property
    def state(self) -> str:
        if self.building:
            return "building"
        return self.outcome or "failed"

    def summary(self) -> dict:
        return {"dossier_id": self.dossier_id, "domain": self.domain, "state": self.state}

    def view(self) -> dict:
        return {**self.summary(), "researched_at": _stamp(self.researched_at),
                "spent_units": self.spent_units, "fields": self.fields}

    def list_item(self) -> dict:
        return {**self.summary(), "legal_name": self.fields["legal_name"]["value"],
                "researched_at": _stamp(self.researched_at), "spent_units": self.spent_units}


def _stamp(value: datetime | None) -> str | None:
    return render(value) if value else None
