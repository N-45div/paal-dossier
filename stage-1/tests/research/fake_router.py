"""An in-process stand-in for ``AsyncWebRouter`` that serves the sample corpus like the mock web does."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from web_router.exceptions import ProviderError

FIXTURES = Path(__file__).parent / "fixtures"
SNIPPET = 300


def load_company(domain: str) -> dict:
    return json.loads((FIXTURES / f"{domain}.json").read_text())


def served_text(page: dict) -> str:
    headers = [f"Kind: {page['kind']}", f"Registrant: {page['lineage']['registrant']}"]
    return "\n".join(headers) + "\n\n" + page["text"]


class FakeRouter:
    """Serves one company at epoch 0; ``fail`` maps a method name to the error to raise instead of answering."""

    def __init__(self, domain: str, fail: dict[str, BaseException] | None = None, research: bool = True) -> None:
        self.company = load_company(domain)
        self.fail = fail or {}
        self.research_enabled = research
        self.calls: list[tuple] = []

    def _pages(self) -> list[dict]:
        return [p for p in self.company["pages"] if 0 in p["epochs"]]

    def _by_url(self, url: str) -> dict | None:
        return next((p for p in self._pages() if p["url"] == url), None)

    async def aclose(self) -> None:
        return None

    async def search(self, query, *, provider, search_depth, max_results=None, **_):
        self.calls.append(("search", provider, search_depth, query))
        if "search" in self.fail:
            raise self.fail["search"]
        pages = [p for p in self._pages() if p.get("searchable", True)]
        pages.sort(key=lambda p: (-self._score(query, p), p["url"]))
        return SimpleNamespace(results=[self._result(p) for p in pages[:10]])

    @staticmethod
    def _score(query: str, page: dict) -> int:
        """Crude keyword relevance: how often each query word occurs in the page's title and text."""
        haystack = f"{page['title']} {page['text']}".lower()
        return sum(haystack.count(word) for word in query.lower().split())

    @staticmethod
    def _result(page: dict) -> SimpleNamespace:
        snippet = page["text"][:SNIPPET]
        return SimpleNamespace(url=page["url"], title=page["title"], description=snippet, content=snippet)

    async def extract(self, urls, *, provider, **_):
        self.calls.append(("extract", provider, urls[0]))
        if "extract" in self.fail:
            raise self.fail["extract"]
        page = self._by_url(urls[0])
        if page is None:
            raise ProviderError(provider, "no URL could be extracted: no page at this URL")
        return SimpleNamespace(documents=[SimpleNamespace(content=served_text(page))])

    async def research(self, query, *, provider, output_schema, timeout=None, **_):
        self.calls.append(("research", provider, query))
        if "research" in self.fail:
            raise self.fail["research"]
        entries = self.company["research"].get("nimble", {}).get("0", []) if self.research_enabled else []
        structured = {name: None for name in output_schema["properties"]}
        structured.update({e["field"]: e["value"] for e in entries})
        citations = [
            SimpleNamespace(url=e["url"], snippet=e["excerpt"], field=f"$.{e['field']}", extra={}) for e in entries
        ]
        return SimpleNamespace(structured=structured, citations=citations)


def http_error(status: int = 500) -> ProviderError:
    cause = SimpleNamespace(status_code=status)
    error = ProviderError("nimble", f"call failed: Error code: {status}", kind="upstream")
    error.status_code = status
    error.original = cause
    return error


def connection_error() -> ProviderError:
    error = ProviderError("nimble", "call failed: Connection error.", kind="upstream")
    error.status_code = None
    return error
