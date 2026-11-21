"""The origin of each gathered page (stage 4, §4 Origins, R4.12-R4.18).

A page's origin is a domain, from the first rule that applies:

1. Its `First-Published-By` domain.
2. When its `Canonical` URL is not its own, the origin of the page at that URL (its original),
   by these rules. The original is fetched from a provider (Rul-S4-3); at most three Canonical
   URLs are followed in a row, and where a fourth would be followed, or no provider serves the
   URL, the host of that URL stands in for the original's origin.
3. The company's domain, when the page is a lookalike.
4. Its registrant.

Pages with the same origin are one source. Originals are fetched once per build and never twice.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.gateway import ServedPage
from app.lineage import host_of, is_lookalike, lineage_of

MAX_CANONICAL_HOPS = 3

Fetch = Callable[[str], Awaitable["ServedPage | None"]]


class OriginResolver:
    """Resolves page origins for one company. ``fetch(url)`` returns the served page at a URL
    (a provider call, paid like any other), or None when no provider serves it."""

    def __init__(self, company_domain: str, fetch: Fetch) -> None:
        self._company = company_domain
        self._fetch = fetch
        self._originals: dict[str, ServedPage | None] = {}

    async def _original(self, url: str) -> ServedPage | None:
        if url not in self._originals:
            self._originals[url] = await self._fetch(url)
        return self._originals[url]

    async def origin(self, page: ServedPage, hops_left: int = MAX_CANONICAL_HOPS) -> str:
        lineage = lineage_of(page.headers, page.url)
        if lineage.first_published_by is not None:
            return lineage.first_published_by
        if lineage.canonical is not None and lineage.canonical != page.url:
            canonical_host = host_of(lineage.canonical)
            if hops_left == 0:
                return canonical_host  # a fourth Canonical URL would be followed
            original = await self._original(lineage.canonical)
            if original is None:
                return canonical_host  # no provider serves the original
            return await self.origin(original, hops_left - 1)
        if is_lookalike(page.headers.get("Kind"), lineage, page.url):
            return self._company
        return lineage.registrant or host_of(page.url) or page.url

    async def resolve(self, pages: list[ServedPage]) -> dict[str, str]:
        """The origin of each page, by URL."""
        return {page.url: await self.origin(page) for page in pages}
