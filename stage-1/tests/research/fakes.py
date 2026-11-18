"""A scripted stand-in for WebRouter's AsyncWebRouter, used by the build tests."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from web_router.exceptions import ProviderError


class HttpStatus(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


def refused(provider: str, status: int) -> ProviderError:
    return ProviderError(provider, f"refused {status}", original=HttpStatus(status))


def lost(provider: str) -> ProviderError:
    return ProviderError(provider, "Request timed out.", original=asyncio.TimeoutError())


class FakeRouter:
    """Serves ``pages`` (url -> served text) and records every call it receives."""

    def __init__(self, pages: dict[str, str], claims: list | None = None) -> None:
        self.pages = pages
        self.claims = claims or []
        self.calls: list[tuple] = []
        self.search_failures: dict[str, list] = {}   # provider -> outcomes to raise first
        self.extract_failures: dict[str, list] = {}
        self.research_failure: Exception | None = None

    async def search(self, query, *, provider, max_results, search_depth, data_apis):
        self.calls.append(("search", provider, query, search_depth))
        queue = self.search_failures.get(provider)
        if queue:
            raise queue.pop(0)
        results = [
            SimpleNamespace(url=u, title="", description=t[:300], content=t[:300])
            for u, t in list(self.pages.items())[:max_results]
        ]
        return SimpleNamespace(results=results)

    async def extract(self, url, *, provider):
        self.calls.append(("extract", provider, url))
        queue = self.extract_failures.get(provider)
        if queue:
            raise queue.pop(0)
        if url not in self.pages:
            raise ProviderError(
                provider,
                f"no URL could be extracted: {url}: the backend fetched nothing and reported status 'fatal'; no page at this URL",
            )
        doc = SimpleNamespace(url=url, content=self.pages[url])
        return SimpleNamespace(documents=[doc], failures=[])

    async def research(self, query, *, provider, output_schema, timeout):
        self.calls.append(("research", provider, query, sorted(output_schema["properties"])))
        if self.research_failure:
            raise self.research_failure
        structured = {c[0]: c[1] for c in self.claims}
        citations = [SimpleNamespace(url=c[2], snippet=c[3], field=f"$.{c[0]}") for c in self.claims]
        return SimpleNamespace(structured=structured, citations=citations)
