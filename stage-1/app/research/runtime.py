"""One WebRouter client per event loop and one in-flight limiter shared by all builds.

Builds share their loop's client, so connections are reused instead of opened per
build. The limiter is thread-safe and loop-independent.
"""
from __future__ import annotations

import asyncio
import threading
import weakref
from dataclasses import dataclass

from web_router import AsyncWebRouter

from .config import Config


class SharedLimiter:
    """Caps provider calls in flight across every build, whatever loop they run on."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._in_flight = 0
        self._lock = threading.Lock()

    @property
    def in_flight(self) -> int:
        return self._in_flight

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


# Calls of concurrent builds run in parallel up to this many sockets in all; builds
# that each wait on 1 s providers must not queue behind one another (R1.83).
MAX_IN_FLIGHT = 200
_LIMITER = SharedLimiter(MAX_IN_FLIGHT)
_PER_LOOP: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Runtime]" = weakref.WeakKeyDictionary()


@dataclass
class Runtime:
    router: AsyncWebRouter
    limiter: SharedLimiter



def _provider_config(config: Config) -> dict:
    provider_config: dict = {"nimble": {"max_retries": 0, "timeout": config.call_timeout}}
    if config.tavily_base_url:
        provider_config["tavily"] = {"api_base_url": config.tavily_base_url}
    return provider_config


def open_runtime(config: Config) -> Runtime:
    """The running loop's runtime, created on first use."""
    loop = asyncio.get_running_loop()
    runtime = _PER_LOOP.get(loop)
    if runtime is None:
        router = AsyncWebRouter("nimble", provider_config=_provider_config(config))
        runtime = _PER_LOOP[loop] = Runtime(router, _LIMITER)
    return runtime
