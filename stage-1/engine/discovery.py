"""Discovery (RL4, RL6, RL19): the support queries, what each search hit carries, and the
order in which candidate URLs get extract slots.

Extract priority (RL19): company-domain host, then a title or snippet that names the
company, then more distinct queries returning the URL, then the best rank, then the URL.
A URL that does not name the company in its title or snippet goes last.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from .support import company_name, names_company

SUPPORT_QUERY_TEMPLATES = (
    "{name} headquarters city",
    "{name} CEO chief executive",
    "{name} founded year",
    "{name} employees headcount",
    "{name} funding raised",
)


def support_queries(domain: str) -> list[str]:
    name = company_name(domain).title()
    return [template.format(name=name) for template in SUPPORT_QUERY_TEMPLATES]


@dataclass(frozen=True)
class Hit:
    """One search result: where it ranked, which query returned it, and what it says."""

    url: str
    rank: int
    query: int
    title: str
    snippet: str
    provider: str  # the provider whose search answered: it served the snippet


@dataclass
class Candidate:
    url: str
    best_rank: int
    queries: set = field(default_factory=set)
    names_company: bool = False
    company_host: bool = False
    snippets: dict = field(default_factory=dict)  # provider -> the snippet that provider served (RL29)

    def priority(self) -> tuple:
        return (not self.company_host, not self.names_company, -len(self.queries), self.best_rank, self.url)


def host_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_company_host(url: str, domain: str) -> bool:
    host = host_of(url)
    return host == domain or host.endswith("." + domain)


def candidates(hits: list[Hit], domain: str) -> list[Candidate]:
    """Distinct URLs from all answered searches, in extract priority order."""
    by_url: dict[str, Candidate] = {}
    for hit in hits:
        candidate = by_url.get(hit.url)
        if candidate is None:
            candidate = by_url[hit.url] = Candidate(url=hit.url, best_rank=hit.rank)
        candidate.best_rank = min(candidate.best_rank, hit.rank)
        candidate.queries.add(hit.query)
        candidate.snippets.setdefault(hit.provider, hit.snippet)
        candidate.names_company = candidate.names_company or names_company(
            f"{hit.title} {hit.snippet}", domain
        )
    for candidate in by_url.values():
        candidate.company_host = is_company_host(candidate.url, domain)
    return sorted(by_url.values(), key=Candidate.priority)
