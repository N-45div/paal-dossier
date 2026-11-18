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
from collections import Counter

from .queries import sibling_queries, variant_queries
from .runtime import Runtime, open_runtime

log = logging.getLogger(__name__)

SECOND_WAVE_MAX = 8
SECOND_WAVE_MAX_LOAD = 60  # skipped while many builds share the providers (R1.83)
SECOND_WAVE_RESERVE = 6  # units kept for extracting what the second wave finds


class BuildRun:
    """Tasks of one build; later tasks (extracts) are spawned by earlier ones (searches)."""

    def __init__(self, domain: str, spend: Callable[[int], None], config: Config,
                 runtime: Runtime) -> None:
        self.domain = domain
        self.config = config
        self.budget = Budget()
        self._limiter = runtime.limiter
        self.gateway = Gateway(runtime, self.budget, spend, config)
        self.evidence = Evidence(domain)
        self._tasks: set[asyncio.Task] = set()
        self._seen_urls: set[str] = set()
        self._fatal: BaseException | None = None
        self._titles: Counter = Counter()
        self._first_wave_pending = 0
        self._started = asyncio.get_running_loop().time()

    def spawn(self, coro: Awaitable) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._settled)

    def _settled(self, task: asyncio.Task) -> None:
        """Forget a finished task; a non-Exception failure (e.g. a cancelled build) ends the build."""
        self._tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None and not isinstance(error, Exception) and self._fatal is None:
            self._fatal = error
            for other in list(self._tasks):
                other.cancel()

    async def run(self) -> dict:
        self.spawn(self._research())
        self.spawn(self._domain_search())
        queries = variant_queries(self.domain)
        self._first_wave_pending = len(queries)
        for query in queries:
            self.spawn(self._first_wave_search(query))
        try:
            await self._join(self.config.build_deadline)
        finally:
            await self._cancel_pending()
        if self._fatal is not None:
            raise self._fatal
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

    async def _first_wave_search(self, query: str) -> None:
        try:
            await self._search(costs.NIMBLE, query)
        finally:
            self._first_wave_pending -= 1
            if self._first_wave_pending == 0:
                self._start_second_wave()

    def _start_second_wave(self) -> None:
        """Spend spare units on queries shaped like the titles already found."""
        early = asyncio.get_running_loop().time() - self._started <= self.config.second_wave_window
        spare = (self.budget.remaining - SECOND_WAVE_RESERVE) // 2
        busy = self._limiter.in_flight > SECOND_WAVE_MAX_LOAD
        if not early or busy or spare <= 0:
            return
        titles = [t for t, _ in self._titles.most_common()]
        name = self.domain.split(".")[0].replace("-", " ").title()
        for query in sibling_queries(self.domain, titles, name, min(spare, SECOND_WAVE_MAX)):
            self.spawn(self._search(costs.NIMBLE, query))

    async def _search(self, provider: str, query: str) -> None:
        try:
            hits = await self.gateway.search(provider, query)
        except (CallFailed, OutOfBudget):
            return
        self._take_hits(provider, hits)

    def _take_hits(self, provider: str, hits) -> None:
        for hit in hits:
            if hit.title:
                self._titles[hit.title] += 1
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
    runtime = open_runtime(config)
    try:
        return await BuildRun(domain, spend, config, runtime).run()
    except Exception:  # a build never raises: it ends with what it has
        log.exception("research build crashed for %s", domain)
        return {"ok": False, "fields": unknown_fields()}

