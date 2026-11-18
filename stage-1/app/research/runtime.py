"""One WebRouter client per build and one in-flight limiter shared by all builds.

Builds may run in separate threads, each with its own event loop, so the limiter
is thread-safe and loop-independent.
"""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass

from web_router import AsyncWebRouter

from .config import Config


class SharedLimiter:
    """Caps provider calls in flight across every build, whatever loop they run on."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._in_flight = 0
        self._lock = threading.Lock()

    async def __aenter__(self) -> None:
        while True:
            with self._lock:
                if self._in_flight < self._limit:
                    self._in_flight += 1
                    return
            await asyncio.sleep(0.02)

    async def __aexit__(self, *exc) -> None:
        with self._lock:
            self._in_flight -= 1


_LIMITER = SharedLimiter(24)


@dataclass
class Runtime:
    router: AsyncWebRouter
    limiter: SharedLimiter

    async def aclose(self) -> None:
        await self.router.aclose()


def _provider_config(config: Config) -> dict:
    provider_config: dict = {"nimble": {"max_retries": 0, "timeout": config.call_timeout}}
    if config.tavily_base_url:
        provider_config["tavily"] = {"api_base_url": config.tavily_base_url}
    return provider_config


def open_runtime(config: Config) -> Runtime:
    router = AsyncWebRouter("nimble", provider_config=_provider_config(config))
    return Runtime(router, _LIMITER)
