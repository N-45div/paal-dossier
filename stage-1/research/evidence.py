"""From gathered pages to field values (stage-1.md section 4, G11): a field holds the value its excerpts support."""

from dataclasses import dataclass

from .fields import FIELDS
from .outcome import unknown_fields
from .sentences import candidate_excerpts
from .support import supports

PROVIDER = "nimble"


@dataclass(frozen=True)
class Evidence:
    field: str
    value: object
    url: str
    excerpt: str


def evidence_from_pages(domain: str, pages: list[tuple[str, str]]) -> list[Evidence]:
    """Every (field, value) that a single excerpt of gathered prose supports, in page order."""
    found: list[Evidence] = []
    for url, text in pages:
        for excerpt in candidate_excerpts(text):
            for field, value in supports(excerpt, domain):
                found.append(Evidence(field, value, url, excerpt))
    return found


def decide_fields(evidence: list[Evidence]) -> dict[str, dict]:
    """Each field holds the value with the most distinct excerpts (first seen wins ties), citing only those."""
    fields = unknown_fields()
    for name in FIELDS:
        by_value: dict[object, list[Evidence]] = {}
        for item in evidence:
            if item.field == name:
                by_value.setdefault(item.value, []).append(item)
        if not by_value:
            continue
        best = max(by_value, key=lambda value: len({(e.url, e.excerpt) for e in by_value[value]}))
        citations = []
        seen = set()
        for item in by_value[best]:
            key = (item.url, item.excerpt)
            if key not in seen:
                seen.add(key)
                citations.append({"url": item.url, "excerpt": item.excerpt, "provider": PROVIDER})
        fields[name] = {"value": best, "citations": citations}
    return fields
