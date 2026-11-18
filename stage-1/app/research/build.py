"""One build: search, extract and research in parallel, then decide the fields."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from . import costs, unknown_fields
from .budget import Budget
from .config import Config
from .decide import decide_fields
from .evidence import Evidence
from .gateway import CallFailed, Gateway, OutOfBudget
from .queries import variant_queries
from .runtime import runtime_for

log = logging.getLogger(__name__)


class BuildRun:
    """Tasks of one build; later tasks (extracts) are spawned by earlier ones (searches)."""

    def __init__(self, domain: str, spend: Callable[[int], None], config: Config) -> None:
        self.domain = domain
        self.config = config
        self.budget = Budget()
        self.gateway = Gateway(runtime_for(config), self.budget, spend, config)
        self.evidence = Evidence(domain)
        self._tasks: set[asyncio.Task] = set()
        self._seen_urls: set[str] = set()
        self._domain_search_done = False

    def spawn(self, coro: Awaitable) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def run(self) -> dict:
        self.spawn(self._research())
        self.spawn(self._domain_search())
        for query in variant_queries(self.domain):
            self.spawn(self._search(costs.NIMBLE, query))
        try:
            await self._join(self.config.build_deadline)
        finally:
            await self._cancel_pending()
        fields = decide_fields(self.evidence.finish())
        return {"ok": self.gateway.successes > 0, "fields": fields}

    async def _join(self, deadline: float) -> None:
        end = asyncio.get_running_loop().time() + deadline
        while self._tasks:
            remaining = end - asyncio.get_running_loop().time()
            if remaining <= 0:
                return
            await asyncio.wait(set(self._tasks), timeout=remaining)

    async def _cancel_pending(self) -> None:
        pending = [t for t in self._tasks if not t.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def _research(self) -> None:
        try:
            response = await self.gateway.research(self.domain)
        except (CallFailed, OutOfBudget):
            return
        self.evidence.add_claims(response.structured, response.citations)

    async def _domain_search(self) -> None:
        """Exactly one answered search whose query is the domain; Tavily only if Nimble refuses."""
        providers = [costs.NIMBLE] + ([costs.TAVILY] if self.config.tavily_enabled else [])
        for provider in providers:
            try:
                hits = await self.gateway.search(provider, self.domain)
            except CallFailed as failed:
                if failed.refused:
                    continue
                return  # lost in flight: the provider may have answered, so no second one
            except OutOfBudget:
                return
            self._take_hits(provider, hits)
            return

    async def _search(self, provider: str, query: str) -> None:
        try:
            hits = await self.gateway.search(provider, query)
        except (CallFailed, OutOfBudget):
            return
        self._take_hits(provider, hits)

    def _take_hits(self, provider: str, hits) -> None:
        for hit in hits:
            self.evidence.add_snippet(hit.url, hit.text, provider)
            if hit.url not in self._seen_urls:
                self._seen_urls.add(hit.url)
                self.spawn(self._extract(provider, hit.url))

    async def _extract(self, provider: str, url: str) -> None:
        providers = [provider] + ([costs.TAVILY] if provider == costs.NIMBLE and self.config.tavily_enabled else [])
        for candidate in providers:
            try:
                text = await self.gateway.extract(candidate, url)
            except CallFailed as failed:
                if failed.refused:
                    continue
                return
            except OutOfBudget:
                return
            if text:
                self.evidence.add_page(url, text, candidate)
            return


async def run_build(domain: str, spend: Callable[[int], None]) -> dict:
    config = Config.from_env()
    try:
        return await BuildRun(domain, spend, config).run()
    except asyncio.CancelledError:
        raise
    except Exception:  # a build never raises: it ends with what it has
        log.exception("research build crashed for %s", domain)
        return {"ok": False, "fields": unknown_fields()}
