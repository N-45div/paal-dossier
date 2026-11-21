"""Nimble calls through WebRouter, each charged to the build's ledger (Rul-3).

Every call reserves its cost before it is issued. The gateway returns ``(value, refused)``:
``value`` is None when the call gave no usable answer, and ``refused`` is True when the
provider answered with an error status (such calls cost nothing and are released).
A call that timed out or lost its connection keeps its charge, because the provider may
have served it.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar

from web_router import (
    AsyncWebRouter,
    ConfigurationError,
    ProviderError,
    ProviderNotInstalledError,
)

try:
    from web_router import ExtractFailedError
except ImportError:  # WebRouter 0.12 has no such class; its failed extracts are plain ProviderErrors

    class ExtractFailedError(ProviderError):  # type: ignore[no-redef]
        """Never raised by WebRouter 0.12; kept so the classification reads the same on both."""

        call_errors: tuple = ()

from app.budget import (
    NIMBLE_EXTRACT_UNITS,
    NIMBLE_RESEARCH_UNITS,
    NIMBLE_SEARCH_LITE_UNITS,
    Ledger,
)
from app.support import split_header

SEARCH_TIMEOUT_S = 30.0
# Rul-S2-5: a call answered 429 is retried after at least 1.05 s, up to four attempts in all.
RATE_LIMIT_WAIT_S = 1.05
RATE_LIMIT_ATTEMPTS = 4
# R4.57 (stage 4): a call answered with a 5xx is retried the same way, after a short wait. An error
# answer costs nothing (R4.61), so the retry costs no units; the attempts stay within the build's
# time bound and the 80-unit cap.
SERVER_ERROR_WAIT_S = 0.2
# §8 (R1.191): a build whose calls each answer within one second ends within 10 seconds. Retries
# that would start after this many seconds of the build are not made, so an all-fail build still ends
# inside that bound, whatever the answers.
RETRY_WINDOW_S = 3.0
EXTRACT_TIMEOUT_S = 30.0
RESEARCH_TIMEOUT_S = 240.0

_PROVIDER = "nimble"
_KEY_VARIABLE = "NIMBLE_API_KEY"

_T = TypeVar("_T")


@dataclass(frozen=True)
class ServedPage:
    """The served text of one page: its URL, its header lines and its prose."""

    url: str
    prose: str
    headers: dict[str, str]


@dataclass(frozen=True)
class CitedClaim:
    """A research citation: the URL it names and the excerpt the provider quoted."""

    url: str
    excerpt: str


def _refused(error: BaseException) -> bool:
    """True when the provider answered with an error status, so nothing was charged."""
    if isinstance(error, ExtractFailedError):
        return bool(error.call_errors) and all(_refused(item) for item in error.call_errors)
    if isinstance(error, ProviderError):
        return error.status_code is not None and 400 <= error.status_code <= 599
    return False


def _rate_limited(error: BaseException) -> bool:
    """True when the provider answered 429 (for a failed extract: when every URL got 429)."""
    if isinstance(error, ExtractFailedError):
        return bool(error.call_errors) and all(_rate_limited(item) for item in error.call_errors)
    return isinstance(error, ProviderError) and error.status_code == 429


def _server_error(error: BaseException) -> bool:
    """True when the provider answered with a 5xx status (for a failed extract: when every URL did)."""
    if isinstance(error, ExtractFailedError):
        return bool(error.call_errors) and all(_server_error(item) for item in error.call_errors)
    return isinstance(error, ProviderError) and error.status_code is not None and 500 <= error.status_code <= 599


def _retry_wait(error: BaseException) -> float | None:
    """How long to wait before retrying the same request, or None when it is not retried: 429 waits
    at least RATE_LIMIT_WAIT_S (Rul-S2-5), a 5xx waits SERVER_ERROR_WAIT_S (R4.57)."""
    if _rate_limited(error):
        return RATE_LIMIT_WAIT_S
    if _server_error(error):
        return SERVER_ERROR_WAIT_S
    return None


def _never_issued(error: BaseException) -> bool:
    """True when the call could not be made at all (missing key, provider not installed)."""
    return isinstance(error, (ConfigurationError, ProviderNotInstalledError))


_router: AsyncWebRouter | None = None


def _client() -> AsyncWebRouter | None:
    """The shared WebRouter client, built on first use; None when the environment cannot make one."""
    global _router
    if _router is None:
        try:
            # The SDK's own retries would issue further charged calls behind the ledger's back.
            _router = AsyncWebRouter(_PROVIDER, provider_config={_PROVIDER: {"max_retries": 0}})
        except (ConfigurationError, ProviderNotInstalledError):
            return None
    return _router


class NimbleGateway:
    """The build's only route to the providers: all calls go through ``web_router``.

    ``on_spend(units)`` is told each reservation just before its call is issued, and
    ``on_spend(-units)`` when a refused call's reservation is released (Rul-11).
    """

    def __init__(self, ledger: Ledger, on_spend: Callable[[int], None] | None = None) -> None:
        self._ledger = ledger
        self._on_spend = on_spend
        self._started = time.monotonic()

    @property
    def available(self) -> bool:
        """False when no Nimble key is configured or no WebRouter client can be made."""
        return bool(os.environ.get(_KEY_VARIABLE, "").strip()) and _client() is not None

    async def _charged(
        self,
        cost: int,
        timeout: float,
        call: Callable[[AsyncWebRouter], Awaitable[_T | None]],
    ) -> tuple[_T | None, bool]:
        """One logical call: retried after 429 and 5xx answers (Rul-S2-5, R4.57), up to
        RATE_LIMIT_ATTEMPTS attempts; each attempt that is billed is charged once."""
        value, refused = None, False
        for attempt in range(1, RATE_LIMIT_ATTEMPTS + 1):
            value, refused, wait = await self._attempt(cost, timeout, call)
            if wait is None or attempt == RATE_LIMIT_ATTEMPTS or not self._within_window(wait):
                break
            await asyncio.sleep(wait)
        return value, refused

    def _within_window(self, wait: float) -> bool:
        """True when a retry after ``wait`` seconds still starts inside RETRY_WINDOW_S of the build."""
        return time.monotonic() - self._started + wait < RETRY_WINDOW_S

    async def _attempt(
        self,
        cost: int,
        timeout: float,
        call: Callable[[AsyncWebRouter], Awaitable[_T | None]],
    ) -> tuple[_T | None, bool, float | None]:
        """Reserve, issue and settle one attempt: (value, refused, wait before a retry or None)."""
        router = _client()
        if router is None or not self._ledger.reserve(cost):
            return None, False, None
        self._notify(cost)
        try:
            return await asyncio.wait_for(call(router), timeout), False, None
        except Exception as error:  # every provider failure is classified below
            if _refused(error) or _never_issued(error):
                self._ledger.release(cost)
                self._notify(-cost)
            return None, _refused(error), _retry_wait(error)

    def _notify(self, units: int) -> None:
        if self._on_spend is not None:
            self._on_spend(units)

    async def search(self, query: str) -> tuple[list[str] | None, bool]:
        """Lite search through Nimble: the result URLs in rank order, or None."""

        async def call(router: AsyncWebRouter) -> list[str]:
            response = await router.search(query, provider=_PROVIDER, search_depth="lite")
            return response.urls

        return await self._charged(NIMBLE_SEARCH_LITE_UNITS, SEARCH_TIMEOUT_S, call)

    async def extract(self, url: str) -> tuple[ServedPage | None, bool]:
        """Full served text of one URL, without rendering; None when no page came back."""

        async def call(router: AsyncWebRouter) -> ServedPage | None:
            response = await router.extract([url], provider=_PROVIDER)
            for document in response.documents:
                headers, prose = split_header(document.content)
                return ServedPage(url=document.url, prose=prose, headers=headers)
            return None

        return await self._charged(NIMBLE_EXTRACT_UNITS, EXTRACT_TIMEOUT_S, call)

    async def research(self, query: str, output_schema: dict[str, Any]) -> tuple[list[CitedClaim] | None, bool]:
        """One research run; its citations, or None when the run gave no answer."""

        async def call(router: AsyncWebRouter) -> list[CitedClaim]:
            response = await router.research(
                query,
                provider=_PROVIDER,
                output_schema=output_schema,
                timeout=RESEARCH_TIMEOUT_S,
            )
            return [CitedClaim(url=item.url, excerpt=item.snippet) for item in response.citations]

        return await self._charged(NIMBLE_RESEARCH_UNITS, RESEARCH_TIMEOUT_S, call)
