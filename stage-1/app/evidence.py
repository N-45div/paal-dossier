"""From gathered pages and research citations to one decision per field (Rul-8, §4).

A candidate is one excerpt that supports one value of one field. Research citations
count only when their excerpt is a verbatim sentence of prose the build gathered for the
cited URL, and when it supports a value under Appendix A. The claim's own value is never
used: the value asserted is the one the excerpt supports.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.gateway import CitedClaim, ServedPage
from app.outcome import FieldResult
from app.support import (
    FIELDS,
    MAX_EXCERPT_LENGTH,
    excerpt_in_prose,
    extract_supports,
    supported_values,
)

MAX_CITATIONS = 3


@dataclass(frozen=True)
class Candidate:
    """One excerpt supporting ``value`` for ``field``, served by ``provider`` at ``url``."""

    field: str
    value: object
    url: str
    excerpt: str
    provider: str


def collect_candidates(
    domain: str,
    pages: list[ServedPage],
    claims: list[CitedClaim],
) -> list[Candidate]:
    """Candidates in gather order: page sentences first, then verified research citations."""
    candidates: list[Candidate] = []
    for page in pages:
        for support in extract_supports(domain, page.prose):
            candidates.append(Candidate(support.field, support.value, page.url, support.excerpt, "nimble"))
    prose_by_url = {page.url: page.prose for page in pages}
    for claim in claims:
        prose = prose_by_url.get(claim.url)
        excerpt = " ".join(claim.excerpt.split())
        if prose is None or not 0 < len(excerpt) <= MAX_EXCERPT_LENGTH:
            continue
        if not excerpt_in_prose(prose, excerpt):
            continue
        for name, value in supported_values(domain, excerpt).items():
            candidates.append(Candidate(name, value, claim.url, excerpt, "nimble"))
    return candidates


def decide_fields(candidates: list[Candidate]) -> dict[str, FieldResult]:
    """Per field: the value supported by the most distinct pages, ties to the earliest excerpt."""
    return {name: _decide(name, candidates) for name in FIELDS}


def _decide(name: str, candidates: list[Candidate]) -> FieldResult:
    groups: dict[object, list[tuple[int, Candidate]]] = {}
    for index, candidate in enumerate(candidates):
        if candidate.field == name:
            groups.setdefault(candidate.value, []).append((index, candidate))
    if not groups:
        return FieldResult()
    value, members = max(
        groups.items(),
        key=lambda item: (len({member.url for _, member in item[1]}), -item[1][0][0]),
    )
    return FieldResult(value=value, citations=_citations(members))


def _citations(members: list[tuple[int, Candidate]]) -> list[dict[str, str]]:
    """Up to three excerpts: one per page first, then any others, in gather order."""
    chosen: list[Candidate] = []
    urls_used: set[str] = set()
    for _, candidate in members:
        if len(chosen) == MAX_CITATIONS:
            break
        if candidate.url not in urls_used:
            chosen.append(candidate)
            urls_used.add(candidate.url)
    for _, candidate in members:
        if len(chosen) == MAX_CITATIONS:
            break
        if candidate not in chosen:
            chosen.append(candidate)
    return [
        {"url": item.url, "excerpt": item.excerpt, "provider": item.provider}
        for item in chosen
    ]
