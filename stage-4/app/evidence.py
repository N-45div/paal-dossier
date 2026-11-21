"""From gathered pages to candidates, and to one transitional decision per field (§4, stage 2).

A candidate is one value of one field that a gathered page supports (Appendix A). Stage 2
keeps every such value: one candidate per (field, value, page), taken from the first
sentence of that page that supports it. A research claim adds no candidate of its own. The
pages a research run cites are gathered and read like any other page, so their sentences
become candidates only through the page itself.
"""

from __future__ import annotations

from app.candidates import Candidate
from app.gateway import ServedPage
from app.outcome import FieldResult
from app.pages import page_meta
from app.investors import investor_names
from app.support import FIELDS, MAX_EXCERPT_LENGTH, extract_supports, prose_sentences, supported_executives

MAX_CITATIONS = 3
PROVIDER = "nimble"


def collect_candidates(domain: str, pages: list[ServedPage],
                       origins: dict[str, str] | None = None) -> dict[str, list[Candidate]]:
    """Every field's candidates, pages in gather order, one per (value, page)."""
    result: dict[str, list[Candidate]] = {name: [] for name in FIELDS}
    seen: set[tuple[str, str, object]] = set()
    for page in pages:
        meta = page_meta(page.headers, page.url, domain)
        for support in extract_supports(domain, page.prose):
            key = (support.field, page.url, support.value)
            if key in seen:
                continue
            seen.add(key)
            result[support.field].append(Candidate(
                value=support.value,
                url=page.url,
                excerpt=support.excerpt,
                provider=PROVIDER,
                kind=meta.kind,
                published_at=meta.published_at,
                true_from=meta.true_from,
                origin=(origins or {}).get(page.url),
            ))
    return result


def collect_executives(domain: str, pages: list[ServedPage],
                       origins: dict[str, str] | None = None) -> list[Candidate]:
    """The `executives` candidates (stage 3): one per (title, name, page), taken from the first
    sentence of that page that supports it (Rul-S2-8, applied per title)."""
    found: list[Candidate] = []
    seen: set[tuple[str, object, str]] = set()
    for page in pages:
        meta = page_meta(page.headers, page.url, domain)
        for sentence in prose_sentences(page.prose):
            if len(sentence) > MAX_EXCERPT_LENGTH:
                continue
            for title, name in supported_executives(domain, sentence).items():
                key = (title, name, page.url)
                if key in seen:
                    continue
                seen.add(key)
                found.append(Candidate(
                    value=name,
                    url=page.url,
                    excerpt=sentence,
                    provider=PROVIDER,
                    kind=meta.kind,
                    published_at=meta.published_at,
                    title=title,
                    true_from=meta.true_from,
                    origin=(origins or {}).get(page.url),
                ))
    return found


def collect_investors(domain: str, pages: list[ServedPage],
                      origins: dict[str, str] | None = None) -> list[Candidate]:
    """The `investors` candidates (stage 4, R4B): one per (name, page), taken from the first
    sentence of that page that supports it. A research claim is never one of these."""
    found: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    for page in pages:
        meta = page_meta(page.headers, page.url, domain)
        for sentence in prose_sentences(page.prose):
            if len(sentence) > MAX_EXCERPT_LENGTH:
                continue
            for name in sorted(investor_names(domain, sentence)):
                key = (name, page.url)
                if key in seen:
                    continue
                seen.add(key)
                found.append(Candidate(
                    value=name,
                    url=page.url,
                    excerpt=sentence,
                    provider=PROVIDER,
                    kind=meta.kind,
                    published_at=meta.published_at,
                    true_from=meta.true_from,
                    origin=(origins or {}).get(page.url),
                ))
    return found


def decide_fields(candidates: dict[str, list[Candidate]]) -> dict[str, FieldResult]:
    """Transitional stage-1 decision (Rul-8) kept for the current dossier layer.

    Per field: the value supported by the most distinct pages, ties to the earliest
    candidate in gather order. Stage 2's selection rule (app/selection.py) replaces this.
    """
    return {name: _decide(candidates.get(name, [])) for name in FIELDS}


def _decide(found: list[Candidate]) -> FieldResult:
    groups: dict[object, list[tuple[int, Candidate]]] = {}
    for index, candidate in enumerate(found):
        groups.setdefault(candidate.value, []).append((index, candidate))
    if not groups:
        return FieldResult()
    value, members = max(
        groups.items(),
        key=lambda item: (len({member.url for _, member in item[1]}), -item[1][0][0]),
    )
    chosen: list[Candidate] = []
    for _, candidate in members:
        if len(chosen) == MAX_CITATIONS:
            break
        if candidate.url not in {item.url for item in chosen}:
            chosen.append(candidate)
    return FieldResult(value=value, citations=[
        {"url": item.url, "excerpt": item.excerpt, "provider": item.provider} for item in chosen
    ])
