"""JSON views of dossiers (spec 8). Callers hold the store lock while building them."""

from datetime import datetime

from dossier.server.model import FIELD_NAMES, Dossier, FieldValue
from dossier.server.timestamps import format_timestamp


def current_state(dossier: Dossier) -> str:
    return "building" if dossier.build is not None else dossier.state


def stamp(instant: datetime | None) -> str | None:
    return format_timestamp(instant) if instant is not None else None


def dossier_ref(dossier: Dossier) -> dict:
    return {"dossier_id": dossier.dossier_id, "domain": dossier.domain, "state": current_state(dossier)}


def dossier_view(dossier: Dossier) -> dict:
    return {
        "dossier_id": dossier.dossier_id,
        "domain": dossier.domain,
        "state": current_state(dossier),
        "researched_at": stamp(dossier.researched_at),
        "spent_units": dossier.spent_units,
        "fields": {name: field_view(dossier.fields[name]) for name in FIELD_NAMES},
    }


def field_view(field: FieldValue) -> dict:
    return {
        "value": field.value,
        "status": "known" if field.value is not None else "unknown",
        "citations": [dict(citation) for citation in field.citations],
    }


def list_row(dossier: Dossier) -> dict:
    return {
        "dossier_id": dossier.dossier_id,
        "domain": dossier.domain,
        "state": current_state(dossier),
        "legal_name": dossier.fields["legal_name"].value,
        "researched_at": stamp(dossier.researched_at),
        "spent_units": dossier.spent_units,
    }
