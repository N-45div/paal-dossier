"""Readers of the stage-1 and stage-2 export dossiers (spec §10, Rul-S2-2). Pure: each reader
validates one dossier object and returns its candidates by field; they raise the same 422 as the
state readers in app.snapshot. Used by the stage-1/2 converters in app.imports."""

from __future__ import annotations

from typing import Any

from app.candidates import PROVIDERS, Candidate, from_citation
from app.clock import parse_rfc3339
from app.errors import validation_failed
from app.candidates import KINDS
from app.support import FIELDS, supported_values


def _obj(entry: Any, what: str) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise validation_failed(f"{what} must be an object")
    return entry


def _text(entry: dict[str, Any], key: str, what: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or value == "":
        raise validation_failed(f"{what}.{key} must be a non-empty string")
    return value


def stage2_candidates(item: dict[str, Any], domain: str) -> dict[str, list[Candidate]]:
    """Candidates of a stage-2 export, validated field by field."""
    raw = _obj(item.get("candidates"), "dossier candidates")
    result: dict[str, list[Candidate]] = {}
    for name in FIELDS:
        entries = raw.get(name)
        if not isinstance(entries, list):
            raise validation_failed(f"candidates of {name} must be a list")
        result[name] = [_stage2_candidate(_obj(e, "candidate")) for e in entries]
    return result


def _stage2_candidate(item: dict[str, Any]) -> Candidate:
    value = item.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, str)) or value == "":
        raise validation_failed("candidate value must be a non-empty string or an integer")
    kind = item.get("kind")
    if kind is not None and kind not in KINDS:
        raise validation_failed("candidate kind is not a known page kind")
    provider = _text(item, "provider", "candidate")
    if provider not in PROVIDERS:
        raise validation_failed("candidate provider is not known")
    published = item.get("published_at")
    if published is not None:
        parse_rfc3339(_text(item, "published_at", "candidate"))
    return Candidate(value=value, url=_text(item, "url", "candidate"),
                     excerpt=_text(item, "excerpt", "candidate"), provider=provider,
                     kind=kind, published_at=published)


def stage1_candidates(item: dict[str, Any], domain: str) -> dict[str, list[Candidate]]:
    """Candidates of a stage-1 export (Rul-S2-2): one per verified citation of each field."""
    fields = _obj(item.get("fields"), "dossier fields")
    result: dict[str, list[Candidate]] = {}
    for name in FIELDS:
        entry = _obj(fields.get(name), f"field {name}")
        value = entry.get("value")
        if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int))):
            raise validation_failed(f"field {name} has an invalid value")
        citations = entry.get("citations")
        if not isinstance(citations, list):
            raise validation_failed(f"field {name} citations must be a list")
        cands: list[Candidate] = []
        for citation in citations:
            cite = _obj(citation, "citation")
            for key in ("url", "excerpt", "provider"):
                _text(cite, key, "citation")
            if value is None:
                continue
            # A stage-1 citation was verified when it was written; keep it only while it
            # still supports the field's value under Appendix A.
            if supported_values(domain, cite["excerpt"]).get(name) == value:
                cands.append(from_citation(value, cite))
        result[name] = cands
    return result
