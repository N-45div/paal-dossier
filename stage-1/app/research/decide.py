"""Choose each field's value from the supported candidates (spec section 4)."""
from __future__ import annotations

from collections import defaultdict

from . import FIELD_NAMES
from .evidence import Candidate

MAX_CITATIONS = 5


def _tie_break(value) -> tuple:
    return (isinstance(value, str), str(value) if isinstance(value, str) else value)


def decide_fields(candidates: list[Candidate]) -> dict:
    """Per field: the value backed by most distinct URLs, cited by one excerpt per URL."""
    fields = {}
    for name in FIELD_NAMES:
        by_value: dict = defaultdict(list)
        for c in candidates:
            if c.field == name:
                by_value[c.value].append(c)
        fields[name] = _field(by_value)
    return fields


def _field(by_value: dict) -> dict:
    if not by_value:
        return {"value": None, "status": "unknown", "citations": []}

    def support(value) -> int:
        return len({c.url for c in by_value[value]})

    best = min(by_value, key=lambda v: (-support(v), _tie_break(v)))
    citations, seen = [], set()
    for c in by_value[best]:
        if c.url not in seen and len(citations) < MAX_CITATIONS:
            seen.add(c.url)
            citations.append({"url": c.url, "excerpt": c.excerpt, "provider": c.provider})
    return {"value": best, "status": "known", "citations": citations}
