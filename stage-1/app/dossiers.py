"""Dossier records: shape, rendering, import validation (§4, §8).

A record keeps the fields of the last build that completed `ready`, the build state
and the spending. Field values are stored as {"value", "citations"}.
"""

from typing import Any

from .domain import normalise_domain
from .errors import validation
from .wire import format_ts, parse_rfc3339

FIELD_NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")
PROVIDERS = ("nimble", "tavily")
BUILD_STATES = ("building", "ready", "failed")
IMPORTABLE_STATES = ("ready", "failed")


def unknown_fields() -> dict[str, dict[str, Any]]:
    return {name: {"value": None, "citations": []} for name in FIELD_NAMES}


def new_record(dossier_id: str, domain: str) -> dict[str, Any]:
    return {
        "dossier_id": dossier_id,
        "domain": domain,
        "state": "building",
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
        if not _is_value(value):
            continue
        citations = [c for c in (entry.get("citations") or []) if _is_citation(c)]
        if not citations:
            continue
        result[name] = {"value": value, "citations": [dict(c) for c in citations]}
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
    legal = record["fields"]["legal_name"]["value"]
    return {
        "dossier_id": record["dossier_id"],
        "domain": record["domain"],
        "state": record["state"],
        "legal_name": legal,
        "researched_at": record["researched_at"],
        "spent_units": record["spent_units"],
    }


def export_dossier(record: dict[str, Any]) -> dict[str, Any]:
    """The exported form: a building dossier is exported as its last completed build (RL10)."""
    state = record["state"]
    if state == "building":
        state = "ready" if record["researched_at"] else "failed"
    return {
        "dossier_id": record["dossier_id"],
        "domain": record["domain"],
        "state": state,
        "researched_at": record["researched_at"],
        "spent_units": record["spent_units"],
        "fields": record["fields"] if record["researched_at"] else unknown_fields(),
    }


def dossier_from_json(entry: dict[str, Any]) -> dict[str, Any]:
    dossier_id = entry.get("dossier_id")
    if not isinstance(dossier_id, str) or not 1 <= len(dossier_id) <= 64:
        raise validation("state holds an invalid dossier id")
    raw_domain = entry.get("domain")
    if not isinstance(raw_domain, str):
        raise validation("state holds an invalid dossier domain")
    domain = normalise_domain(raw_domain)
    if domain != raw_domain:
        raise validation("state holds a dossier domain that is not normalised")
    state = entry.get("state")
    if state not in IMPORTABLE_STATES:
        raise validation("state holds a dossier in a state that cannot be imported")
    researched_raw = entry.get("researched_at")
    if researched_raw is None:
        if state == "ready":
            raise validation("a ready dossier needs researched_at")
        researched_at = None
    else:
        moment = parse_rfc3339(researched_raw)
        if moment is None or state != "ready":
            raise validation("state holds an invalid researched_at")
        researched_at = format_ts(moment)
    spent = entry.get("spent_units")
    if not isinstance(spent, int) or isinstance(spent, bool) or spent < 0:
        raise validation("state holds an invalid spent_units")
    fields = entry.get("fields")
    if not isinstance(fields, dict) or set(fields) != set(FIELD_NAMES):
        raise validation("state holds dossier fields that are not the six fields")
    return {
        "dossier_id": dossier_id,
        "domain": domain,
        "state": state,
        "researched_at": researched_at,
        "spent_units": spent,
        "fields": {name: _field_from_json(fields[name]) for name in FIELD_NAMES},
    }


def _field_from_json(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise validation("state holds an invalid field")
    value = entry.get("value")
    citations = entry.get("citations")
    if not isinstance(citations, list):
        raise validation("state holds an invalid citation list")
    if value is None:
        if citations:
            raise validation("an unknown field cannot have citations")
        return {"value": None, "citations": []}
    if not _is_value(value) or not citations or not all(_is_citation(c) for c in citations):
        raise validation("state holds an invalid field value")
    return {"value": value, "citations": [dict(c) for c in citations]}


def _render_field(field: dict[str, Any]) -> dict[str, Any]:  # noqa: D401 - rendering helper
    value = field["value"]
    return {
        "value": value,
        "status": "known" if value is not None else "unknown",
        "citations": [dict(c) for c in field["citations"]],
    }


def _is_value(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, (str, int))


def _is_citation(entry: Any) -> bool:
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("url"), str)
        and isinstance(entry.get("excerpt"), str)
        and entry.get("provider") in PROVIDERS
    )


