"""Dossier records: shape, rendering, import validation (§4, §8, RL17).

A record keeps the fields of the last build that completed `ready`, the build state
and the spending. A field is stored as {"value", "status", "citations", "candidates"}:
`status` is one of known, contested, unknown (R2.47-R2.50); `candidates` lists the
build's candidates in rank order, the selected one first (R2.32-R2.38). The selection
itself is made by the engine (RL62); this module only stores and checks its result.
"""

from typing import Any

from .domain import normalise_domain
from engine.selection import assemble_field

from .errors import validation
from .wire import format_ts, parse_rfc3339

FIELD_NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")
FIELD_TYPES = {"legal_name": str, "hq_city": str, "ceo": str, "founded_year": int, "headcount_range": str, "funding_total": int}
HEADCOUNT_RANGES = ("1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+")
PROVIDERS = ("nimble", "tavily")
IMPORTABLE_STATES = ("ready", "failed")
STATUSES = ("known", "contested", "unknown")
CANDIDATE_KINDS = ("own", "filing", "news", "aggregator", None)
DOSSIER_KEYS = frozenset({"dossier_id", "domain", "state", "researched_at", "spent_units", "fields"})
FIELD_REQUIRED_KEYS = frozenset({"value", "citations"})
FIELD_OPTIONAL_KEYS = frozenset({"status", "candidates"})
CITATION_KEYS = frozenset({"url", "excerpt", "provider"})
CANDIDATE_KEYS = frozenset({"value", "url", "excerpt", "provider", "kind", "published_at", "retrieved_at", "selected"})


def unknown_field() -> dict[str, Any]:
    return {"value": None, "status": "unknown", "citations": [], "candidates": []}


def unknown_fields() -> dict[str, dict[str, Any]]:
    return {name: unknown_field() for name in FIELD_NAMES}


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


def fields_from_engine(raw: Any, retrieved_at: str | None = None) -> dict[str, dict[str, Any]]:
    """Turn a build's fields into stored fields; anything not well formed counts as unknown.

    retrieved_at is the build's time, stamped on candidates derived here (RL-P6 fallback).
    """
    result = unknown_fields()
    if not isinstance(raw, dict):
        return result
    for name in FIELD_NAMES:
        entry = raw.get(name)
        if isinstance(entry, dict):
            stored = _engine_field(name, entry, retrieved_at)
            if stored is not None:
                result[name] = stored
    return result


def _engine_field(name: str, entry: dict, retrieved_at: str | None) -> dict[str, Any] | None:
    """One field as the engine returned it, or None when it is not a usable known/contested field.

    Without candidates (a stage-1 style result), the field is derived per RL59 from its citations.
    """
    value = entry.get("value")
    citations = [_citation_from_engine(c) for c in (entry.get("citations") or []) if _is_citation(c)]
    if not _is_value(name, value) or not citations:
        return None
    if "candidates" not in entry:
        return _derived_field(value, citations, retrieved_at or "")
    status = entry.get("status")
    if status not in ("known", "contested"):
        return None
    candidates = [_candidate_from_engine(c) for c in (entry["candidates"] or []) if _is_candidate(name, c)]
    if not candidates:
        return None
    return {"value": value, "status": status, "citations": citations, "candidates": candidates}


def _derived_field(value: Any, citations: list[dict], retrieved_at: str) -> dict[str, Any]:
    """RL59: one candidate per citation (kind and published time unknown), then the selection rule.

    The value, status, citations and candidates all come from assemble_field, as after a build.
    """
    candidates = [
        {
            "value": value,
            "url": citation["url"],
            "excerpt": citation["excerpt"],
            "provider": citation["provider"],
            "kind": None,
            "published_at": None,
            "retrieved_at": retrieved_at,
            "selected": False,
        }
        for citation in citations
    ]
    assembled = assemble_field(candidates, retrieved_at)
    return {
        "value": assembled["value"],
        "status": assembled["status"],
        "citations": assembled["citations"],
        "candidates": assembled["candidates"],
    }


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
    return {name: _render_field(record["fields"][name]) for name in FIELD_NAMES}


def _exported_unknown() -> dict[str, dict[str, Any]]:
    return {name: _render_field(unknown_field()) for name in FIELD_NAMES}


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
    fields = {name: _field_from_json(name, fields_raw[name], researched_at) for name in FIELD_NAMES}
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


def _field_from_json(name: str, entry: Any, researched_at: str | None) -> dict[str, Any]:
    """Field check on import (RL22.4, RL32): {value, citations} with optional status and candidates.

    A present status must be one of the three and agree with the value: unknown exactly when there
    is no value. Candidates, when present, must be well formed candidates of this field.
    """
    if not isinstance(entry, dict):
        raise validation("state holds an invalid field")
    keys = set(entry)
    if not FIELD_REQUIRED_KEYS <= keys <= FIELD_REQUIRED_KEYS | FIELD_OPTIONAL_KEYS:
        raise validation("state holds an invalid field")
    value = entry["value"]
    citations = entry["citations"]
    candidates = entry.get("candidates", [])
    if not isinstance(citations, list) or not isinstance(candidates, list):
        raise validation("state holds an invalid citation list")
    if value is None:
        if citations != [] or candidates != []:
            raise validation("an unknown field has no value, citations or candidates")
        if entry.get("status", "unknown") != "unknown":
            raise validation("state holds an invalid field status")
        return unknown_field()
    status = entry.get("status", "known")
    if status not in ("known", "contested"):
        raise validation("state holds an invalid field status")
    if not _is_value(name, value) or not citations:
        raise validation("state holds an invalid known field")
    if not all(isinstance(c, dict) and set(c) == CITATION_KEYS and _is_citation(c) for c in citations):
        raise validation("state holds an invalid citation")
    if "candidates" in entry:
        if not all(_is_candidate(name, c) for c in candidates):
            raise validation("state holds an invalid candidate")
        candidates = [_candidate_from_engine(c) for c in candidates]
    else:
        # An export without candidates (stage-1 form) is derived on import (RL59).
        return _derived_field(value, [dict(c) for c in citations], researched_at or "")
    return {
        "value": value,
        "status": status,
        "citations": [dict(c) for c in citations],
        "candidates": candidates,
    }


def _render_field(field: dict[str, Any]) -> dict[str, Any]:
    return {
        "value": field["value"],
        "status": field["status"],
        "citations": [dict(c) for c in field["citations"]],
        "candidates": [dict(c) for c in field["candidates"]],
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


def _is_candidate(name: str, entry: Any) -> bool:
    """A candidate has exactly the Candidates keys (R2.33-R2.37); its value is a value of the field."""
    return (
        isinstance(entry, dict)
        and set(entry) == CANDIDATE_KEYS
        and _is_value(name, entry["value"])
        and _is_citation(entry)
        and entry["kind"] in CANDIDATE_KINDS
        and (entry["published_at"] is None or isinstance(entry["published_at"], str))
        and isinstance(entry["retrieved_at"], str)
        and isinstance(entry["selected"], bool)
    )


def _candidate_from_engine(entry: dict) -> dict[str, Any]:
    return {key: entry[key] for key in CANDIDATE_KEYS}
