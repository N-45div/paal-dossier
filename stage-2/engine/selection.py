"""The selection rule for competing candidates (stage 2, RL62).

Pure functions only. The app and the stage-2 import both call assemble_field; there is no other
implementation of the rule. A candidate is a dict with: value, url, excerpt, provider, kind
(own, filing, news, aggregator, or None for an imported candidate), published_at (RFC 3339
string or None), and retrieved_at (not used for ranking).
"""

from __future__ import annotations

import json
from functools import cmp_to_key
from typing import Any, Optional

from .timestamps import instant

# Authority of a page's kind; None (an imported candidate) has the authority of aggregator.
AUTHORITY = {"own": 3, "filing": 3, "news": 2, "aggregator": 1}
PROVIDER_ORDER = {"nimble": 0, "tavily": 1, "kernel": 2, "browserbase": 3}


def normalise_value(value: Any) -> Any:
    """A value with surrounding whitespace removed from strings; other values unchanged."""
    if isinstance(value, str):
        return value.strip()
    return value


def same_value(first: Any, second: Any) -> bool:
    """Two values are the same when JSON-equal after normalisation. A bool is not an integer."""
    return value_identity(first) == value_identity(second)


def value_identity(value: Any) -> str:
    """A canonical string for a value: equal strings mean the same value (RL71)."""
    return json.dumps(normalise_value(value), sort_keys=True, ensure_ascii=False)


def _authority(kind: Optional[str]) -> int:
    return AUTHORITY.get(kind, AUTHORITY["aggregator"])


def _published(published_at: Optional[str]) -> Optional[tuple]:
    """The exact instant of an RFC 3339 publication time (RL66), or None."""
    return instant(published_at)


def _value_order(value: Any) -> tuple:
    """Integers compare as numbers, strings by code point; other kinds sort after them."""
    value = normalise_value(value)
    if isinstance(value, bool):
        return (2, int(value))
    if isinstance(value, int):
        return (0, value)
    if isinstance(value, str):
        return (1, value)
    return (3, json.dumps(value, sort_keys=True, ensure_ascii=False))


def _compare(first: dict, second: dict) -> int:
    """Negative when first ranks higher than second."""
    authority_difference = _authority(second.get("kind")) - _authority(first.get("kind"))
    if authority_difference:
        return authority_difference
    first_time, second_time = _published(first.get("published_at")), _published(second.get("published_at"))
    if (first_time is None) != (second_time is None):
        return 1 if first_time is None else -1  # a candidate with a time ranks above one without
    if first_time is not None and first_time != second_time:
        return -1 if first_time > second_time else 1
    if first["url"] != second["url"]:
        return -1 if first["url"] < second["url"] else 1
    first_provider = PROVIDER_ORDER.get(first["provider"], len(PROVIDER_ORDER))
    second_provider = PROVIDER_ORDER.get(second["provider"], len(PROVIDER_ORDER))
    if first_provider != second_provider:
        return first_provider - second_provider
    first_value, second_value = _value_order(first["value"]), _value_order(second["value"])
    if first_value != second_value:
        return -1 if first_value < second_value else 1
    return 0


def rank(candidates: list[dict]) -> list[dict]:
    """The candidates in rank order, highest first (R2.40-R2.46). Does not modify its input."""
    return sorted(candidates, key=cmp_to_key(_compare))


def status_of(candidates: list[dict]) -> str:
    """known: candidates exist with one value; contested: two or more values; unknown: none."""
    if not candidates:
        return "unknown"
    distinct = {value_identity(candidate["value"]) for candidate in candidates}
    return "known" if len(distinct) == 1 else "contested"


def assemble_field(candidates: list[dict], retrieved_at: str) -> dict:
    """{"value", "status", "citations", "candidates"} for one field (RL62, Candidates, Status).

    candidates lists every candidate in rank order with selected true only on index 0; each
    candidate carries the given retrieved_at. citations are the url, excerpt and provider of
    every candidate sharing the selected value, in rank order.
    """
    ranked = rank(candidates)
    if not ranked:
        return {"value": None, "status": "unknown", "citations": [], "candidates": []}
    selected_value = normalise_value(ranked[0]["value"])
    listed = []
    for index, candidate in enumerate(ranked):
        listed.append(
            {
                "value": normalise_value(candidate["value"]),
                "url": candidate["url"],
                "excerpt": candidate["excerpt"],
                "provider": candidate["provider"],
                "kind": candidate.get("kind"),
                "published_at": candidate.get("published_at"),
                "retrieved_at": retrieved_at,
                "selected": index == 0,
            }
        )
    citations = [
        {"url": item["url"], "excerpt": item["excerpt"], "provider": item["provider"]}
        for item in listed
        if same_value(item["value"], selected_value)
    ]
    return {
        "value": selected_value,
        "status": status_of(ranked),
        "citations": citations,
        "candidates": listed,
    }
