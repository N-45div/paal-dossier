"""The six dossier fields (§4)."""
from __future__ import annotations

from typing import Any

FIELD_NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")


def unknown_field() -> dict[str, Any]:
    return {"value": None, "status": "unknown", "citations": []}


def unknown_fields() -> dict[str, dict[str, Any]]:
    return {name: unknown_field() for name in FIELD_NAMES}


def clean_field(candidate: Any) -> dict[str, Any]:
    """Return a well-formed field; anything inconsistent becomes unknown."""
    if not isinstance(candidate, dict):
        return unknown_field()
    value = candidate.get("value")
    citations = candidate.get("citations")
    if value is None or not isinstance(citations, list) or not citations:
        return unknown_field()
    kept = []
    for citation in citations:
        if not isinstance(citation, dict):
            return unknown_field()
        url, excerpt, provider = citation.get("url"), citation.get("excerpt"), citation.get("provider")
        if not (isinstance(url, str) and isinstance(excerpt, str) and isinstance(provider, str)):
            return unknown_field()
        kept.append({"url": url, "excerpt": excerpt, "provider": provider})
    return {"value": value, "status": "known", "citations": kept}


def clean_fields(candidate: Any) -> dict[str, dict[str, Any]]:
    source = candidate if isinstance(candidate, dict) else {}
    return {name: clean_field(source.get(name)) for name in FIELD_NAMES}
