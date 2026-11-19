"""Dossier records: shape, rendering, import validation (§4, §8, RL17).

A record keeps the fields of the last build that completed `ready`, the build state
and the spending. Field values are stored as {"value", "citations"}.
"""

from typing import Any

from .domain import normalise_domain
from .errors import validation
from .wire import format_ts, parse_rfc3339

FIELD_NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")
FIELD_TYPES = {"legal_name": str, "hq_city": str, "ceo": str, "founded_year": int, "headcount_range": str, "funding_total": int}
HEADCOUNT_RANGES = ("1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+")
PROVIDERS = ("nimble", "tavily")
IMPORTABLE_STATES = ("ready", "failed")
DOSSIER_KEYS = frozenset({"dossier_id", "domain", "state", "researched_at", "spent_units", "fields"})
FIELD_KEYS = frozenset({"value", "status", "citations"})  # RL22.4: exactly these three
CITATION_KEYS = frozenset({"url", "excerpt", "provider"})


def unknown_fields() -> dict[str, dict[str, Any]]:
    return {name: {"value": None, "citations": []} for name in FIELD_NAMES}


def new_record(dossier_id: str, domain: str) -> dict[str, Any]:
    return {
        "dossier_id": dossier_id,
        "domain": domain,
        "state": "building",
        "last_state": None,  # outcome of the last completed build: ready, failed, or None if none yet
        "researched_at": None,
        "spent_units": 0,
        "fields": unknown_fields(),
    }


def fields_from_engine(raw: Any) -> dict[str, dict[str, Any]]:
    """Turn a build's fields into stored fields; anything not well formed counts as unknown."""
    result = unknown_fields()
    if not isinstance(raw, dict):
        return result
    for name in FIELD_NAMES:
        entry = raw.get(name)
        if not isinstance(entry, dict):
            continue
        value = entry.get("value")
        if not _is_value(name, value):
            continue
        citations = [_citation_from_engine(c) for c in (entry.get("citations") or []) if _is_citation(c)]
        if not citations:
            continue
        result[name] = {"value": value, "citations": citations}
    return result


def render(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "dossier_id": record["dossier_id"],
        "domain": record["domain"],
        "state": record["state"],
        "researched_at": record["researched_at"],
        "spent_units": record["spent_units"],
        "fields": {name: _render_field(record["fields"][name]) for name in FIELD_NAMES},
    }


def summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "dossier_id": record["dossier_id"],
        "domain": record["domain"],
        "state": record["state"],
        "legal_name": record["fields"]["legal_name"]["value"],
        "researched_at": record["researched_at"],
        "spent_units": record["spent_units"],
    }


def export_dossier(record: dict[str, Any]) -> dict[str, Any]:
    """The exported form: a building dossier is exported as its last completed build (RL10)."""
    state = record["state"]
    if state == "building":
        state = record["last_state"] or "failed"
    return {
        "dossier_id": record["dossier_id"],
        "domain": record["domain"],
        "state": state,
        "researched_at": record["researched_at"],
        "spent_units": record["spent_units"],
        "fields": _exported_fields(record) if record["researched_at"] else _exported_unknown(),
    }


def _exported_fields(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {name: _exported_field(record["fields"][name]) for name in FIELD_NAMES}


def _exported_unknown() -> dict[str, dict[str, Any]]:
    return {name: _exported_field({"value": None, "citations": []}) for name in FIELD_NAMES}


def _exported_field(field: dict[str, Any]) -> dict[str, Any]:
    value = field["value"]
    return {
        "value": value,
        "status": "known" if value is not None else "unknown",
        "citations": [dict(c) for c in field["citations"]],
    }


def dossier_from_json(entry: Any) -> dict[str, Any]:
    """Structural check of one exported dossier (RL17); the stored record it returns is safe to keep."""
    if not isinstance(entry, dict) or set(entry) != DOSSIER_KEYS:
        raise validation("state dossiers must have exactly the expected keys")
    dossier_id = entry["dossier_id"]
    if not isinstance(dossier_id, str) or not 1 <= len(dossier_id) <= 64:
        raise validation("state holds an invalid dossier id")
    raw_domain = entry["domain"]
    if not isinstance(raw_domain, str) or normalise_domain(raw_domain) != raw_domain:
        raise validation("state holds an invalid dossier domain")
    state = entry["state"]
    if state not in IMPORTABLE_STATES:
        raise validation("state holds a dossier in a state that cannot be imported")
    spent = entry["spent_units"]
    if not isinstance(spent, int) or isinstance(spent, bool) or not 0 <= spent <= 10**12:
        raise validation("state holds an invalid spent_units")
    researched_raw = entry["researched_at"]
    if researched_raw is None:
        researched_at = None
    else:
        moment = parse_rfc3339(researched_raw)
        if moment is None:
            raise validation("state holds an invalid researched_at")
        researched_at = format_ts(moment)
    if state == "ready" and researched_at is None:
        raise validation("a ready dossier needs researched_at")
    fields_raw = entry["fields"]
    if not isinstance(fields_raw, dict) or set(fields_raw) != set(FIELD_NAMES):
        raise validation("state holds dossier fields that are not the six fields")
    fields = {name: _field_from_json(name, fields_raw[name]) for name in FIELD_NAMES}
    if researched_at is None and any(f["value"] is not None for f in fields.values()):
        raise validation("known fields need researched_at")
    return {
        "dossier_id": dossier_id,
        "domain": raw_domain,
        "state": state,
        "last_state": state,
        "researched_at": researched_at,
        "spent_units": spent,
        "fields": fields,
    }


def _field_from_json(name: str, entry: Any) -> dict[str, Any]:
    """Strict field check (RL22.4): exact keys, status iff value, typed value, well-formed citations."""
    if not isinstance(entry, dict) or set(entry) != FIELD_KEYS:
        raise validation("state holds an invalid field")
    value = entry["value"]
    status = entry["status"]
    citations = entry["citations"]
    if not isinstance(citations, list):
        raise validation("state holds an invalid citation list")
    if value is None:
        if status != "unknown" or citations != []:
            raise validation("an unknown field has no value, no citations and status unknown")
        return {"value": None, "citations": []}
    if status != "known" or not _is_value(name, value) or not citations:
        raise validation("state holds an invalid known field")
    if not all(isinstance(c, dict) and set(c) == CITATION_KEYS and _is_citation(c) for c in citations):
        raise validation("state holds an invalid citation")
    return {"value": value, "citations": [dict(c) for c in citations]}


def _render_field(field: dict[str, Any]) -> dict[str, Any]:
    value = field["value"]
    return {
        "value": value,
        "status": "known" if value is not None else "unknown",
        "citations": [dict(c) for c in field["citations"]],
    }


def _is_value(name: str, value: Any) -> bool:
    """A value of the field's type; a bool is never an int value, and headcount is one of the ranges."""
    if value is None or isinstance(value, bool):
        return False
    if not isinstance(value, FIELD_TYPES[name]):
        return False
    if name == "founded_year":
        return 1800 <= value <= 2099
    if name == "funding_total":
        return value >= 0  # RL24: $0 is an amount that normalises to 0 (A.4/A.5); negatives are not
    if name in ("legal_name", "hq_city", "ceo"):
        return value != "" and value == value.strip()
    if name == "headcount_range":
        return value in HEADCOUNT_RANGES
    if isinstance(value, str):
        return value != "" and value == value.strip()
    return value >= 0


def _is_citation(entry: Any) -> bool:
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("url"), str)
        and entry.get("url") != ""
        and isinstance(entry.get("excerpt"), str)
        and 1 <= len(entry.get("excerpt")) <= 500
        and entry.get("provider") in PROVIDERS
    )


def _citation_from_engine(entry: dict) -> dict[str, str]:
    return {"url": entry["url"], "excerpt": entry["excerpt"], "provider": entry["provider"]}
