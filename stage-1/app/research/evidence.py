"""Turn gathered page texts and research claims into the six fields of a dossier (§4, L1.11, L1.12)."""

from __future__ import annotations

from dataclasses import dataclass

from app.research.pages import ServedText, prose_sentences
from app.research.providers import Claim, Gathered
from app.research.support import FIELDS, Value, supported_values, supports

MAX_CITATIONS = 5


@dataclass(frozen=True)
class Candidate:
    field: str
    value: Value
    url: str
    excerpt: str
    provider: str


def page_candidates(texts: list[ServedText], domain: str) -> list[Candidate]:
    """Every sentence of every served prose that supports a value, in the order gathered."""
    found = []
    for served in texts:
        for sentence in prose_sentences(served):
            for field, value in supported_values(sentence, domain).items():
                found.append(Candidate(field, value, served.url, sentence, served.provider))
    return found


def claim_candidates(claims: list[Claim], domain: str) -> list[Candidate]:
    """Research claims, asserted only when their own citation supports them (L1.11)."""
    return [
        Candidate(c.field, c.value, c.url, " ".join(c.excerpt.split()), "nimble")
        for c in claims
        if supports(" ".join(c.excerpt.split()), domain, c.field, c.value) and 1 <= len(" ".join(c.excerpt.split())) <= 500
    ]


def _unknown() -> dict:
    return {"value": None, "status": "unknown", "citations": []}


def _citations(candidates: list[Candidate]) -> list[dict]:
    """At most MAX_CITATIONS citations: one per distinct URL first, then further excerpts."""
    first_per_url = list({c.url: c for c in reversed(candidates)}.values())[::-1]
    rest = [c for c in candidates if c not in first_per_url]
    chosen = (first_per_url + rest)[:MAX_CITATIONS]
    return [{"url": c.url, "excerpt": c.excerpt, "provider": c.provider} for c in chosen]


def decide_field(candidates: list[Candidate]) -> dict:
    """The value with most supporting URLs (ties: first gathered), cited by excerpts supporting it."""
    if not candidates:
        return _unknown()
    urls_by_value: dict[Value, set[str]] = {}
    for candidate in candidates:
        urls_by_value.setdefault(candidate.value, set()).add(candidate.url)
    best = max(urls_by_value, key=lambda v: len(urls_by_value[v]))  # max keeps the first of equals
    chosen = [c for c in candidates if c.value == best]
    return {"value": best, "status": "known", "citations": _citations(chosen)}


def build_fields(gathered: Gathered, domain: str) -> dict[str, dict]:
    """The six fields from everything a build has gathered."""
    candidates = page_candidates(gathered.texts, domain) + claim_candidates(gathered.claims, domain)
    return {field: decide_field([c for c in candidates if c.field == field]) for field in FIELDS}
