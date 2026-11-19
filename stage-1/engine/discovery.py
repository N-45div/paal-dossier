"""Discovery plan (RL4, RL6): the support queries and the order in which to extract URLs."""

from __future__ import annotations

from urllib.parse import urlparse

from .support import company_name

SUPPORT_QUERY_TEMPLATES = (
    "{name} headquarters city",
    "{name} CEO chief executive",
    "{name} founded year",
    "{name} employees headcount",
    "{name} funding raised",
    "{name} legal name registered",
)


def support_queries(domain: str) -> list[str]:
    name = company_name(domain).title()
    return [template.format(name=name) for template in SUPPORT_QUERY_TEMPLATES]


def host_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_company_host(url: str, domain: str) -> bool:
    host = host_of(url)
    return host == domain or host.endswith("." + domain)


def rank_urls(hits: list[tuple[str, int]], domain: str) -> list[str]:
    """Distinct URLs, company pages first, then by best (lowest) rank, then by URL.

    ``hits`` holds (url, rank) pairs from every search that answered.
    """
    best: dict[str, int] = {}
    for url, rank in hits:
        if url not in best or rank < best[url]:
            best[url] = rank
    return sorted(best, key=lambda url: (not is_company_host(url, domain), best[url], url))
