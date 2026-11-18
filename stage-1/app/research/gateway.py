"""Every provider call of one build goes through here, via WebRouter.

The gateway reserves a call's units before sending it, gives them back when
the provider refuses the call with an error status (which costs nothing), and
reports the cost to ``spend`` for every other outcome, timeouts included.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from web_router.exceptions import (
    ConfigurationError, ProviderError, ProviderNotFoundError, ProviderNotInstalledError,
)

from . import costs
from .budget import Budget
from .config import Config
from .runtime import Runtime

FIELD_SCHEMA_TYPES = {
    "legal_name": "string", "hq_city": "string", "ceo": "string",
    "founded_year": "integer", "headcount_range": "string", "funding_total": "integer",
}
RESEARCH_QUERY = (
    "Research the company {domain}. Find its legal name, headquarters city, chief executive, "
    "founding year, headcount range and total equity funding raised."
)
MAX_RATE_LIMIT_RETRIES = 3
RATE_LIMIT_WAIT = 1.1
SERVER_ERROR_WAIT = 0.5
_NOT_SENT = (ConfigurationError, ProviderNotFoundError, ProviderNotInstalledError)


class OutOfBudget(Exception):
    """The call would take the build past its unit cap; nothing was sent."""


class _NoPage(Exception):
    """The provider answered, but has no page for the URL (not a refusal)."""


class CallFailed(Exception):
    """The call produced no answer: refused with an error status, or lost."""

    def __init__(self, status: int | None = None, refused: bool = False) -> None:
        super().__init__(f"call failed (status {status})")
        self.status = status
        self.refused = refused


@dataclass(frozen=True)
class Hit:
    url: str
    text: str


class Gateway:
    def __init__(self, runtime: Runtime, budget: Budget, spend: Callable[[int], None],
                 config: Config) -> None:
        self._runtime = runtime
        self._budget = budget
        self._spend = spend
        self._config = config
        self.successes = 0

    async def search(self, provider: str, query: str, depth: str = "lite") -> list[Hit]:
        router = self._runtime.router
        response = await self._call(
            costs.search_cost(provider, depth), self._config.call_timeout,
            lambda: router.search(query, provider=provider, max_results=10,
                                  search_depth=depth, data_apis=False),
        )
        return [Hit(r.url, r.content or r.description or "") for r in response.results if r.url]

    async def extract(self, provider: str, url: str) -> str | None:
        """The served text of ``url``, or None when the provider has no page for it."""
        router = self._runtime.router
        try:
            response = await self._call(
                costs.extract_cost(provider), self._config.call_timeout,
                lambda: router.extract(url, provider=provider),
            )
        except _NoPage:
            return None
        return next((d.content for d in response.documents if d.content), None)

    async def research(self, domain: str) -> Any:
        router = self._runtime.router
        schema = {
            "type": "object",
            "properties": {f: {"type": [t, "null"]} for f, t in FIELD_SCHEMA_TYPES.items()},
        }
        return await self._call(
            costs.NIMBLE_RESEARCH, self._config.research_timeout + 2,
            lambda: router.research(
                RESEARCH_QUERY.format(domain=domain), provider=costs.NIMBLE,
                output_schema=schema, timeout=self._config.research_timeout),
        )

    async def _call(self, cost: int, timeout: float, make: Callable[[], Awaitable[Any]]) -> Any:
        rate_limited = server_errors = 0
        while True:
            try:
                return await self._attempt(cost, timeout, make)
            except CallFailed as failed:
                if not failed.refused:
                    raise
                if failed.status == 429 and rate_limited < MAX_RATE_LIMIT_RETRIES:
                    rate_limited += 1
                    wait = RATE_LIMIT_WAIT
                elif failed.status and failed.status >= 500 and server_errors < 1:
                    server_errors += 1
                    wait = SERVER_ERROR_WAIT
                else:
                    raise
                await asyncio.sleep(wait)

    async def _attempt(self, cost: int, timeout: float, make: Callable[[], Awaitable[Any]]) -> Any:
        if not self._budget.reserve(cost):
            raise OutOfBudget()
        charged = False
        try:
            async with self._runtime.limiter:
                charged = True
                result = await asyncio.wait_for(make(), timeout)
            self.successes += 1
            return result
        except ProviderError as exc:
            if exc.status_code is None:
                raise CallFailed() from exc
            if exc.original is None:  # answered, but had no page: not a refusal
                self.successes += 1
                raise _NoPage() from exc
            charged = False
            raise CallFailed(exc.status_code, refused=True) from exc
        except _NOT_SENT as exc:
            charged = False
            raise CallFailed(refused=False) from exc
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # timeouts and anything else: the call may have been received
            raise CallFailed() from exc
        finally:
            if charged:
                self._spend(cost)
            else:
                self._budget.release(cost)
