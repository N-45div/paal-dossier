"""One WebRouter client and one in-flight limiter per event loop."""
from __future__ import annotations

import asyncio
import weakref
from dataclasses import dataclass

from web_router import AsyncWebRouter

from .config import Config

_PER_LOOP: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Runtime]" = weakref.WeakKeyDictionary()


@dataclass
class Runtime:
    router: AsyncWebRouter
    limiter: asyncio.Semaphore


def _provider_config(config: Config) -> dict:
    provider_config: dict = {"nimble": {"max_retries": 0, "timeout": config.call_timeout}}
    if config.tavily_base_url:
        provider_config["tavily"] = {"api_base_url": config.tavily_base_url}
    return provider_config


def runtime_for(config: Config) -> Runtime:
    loop = asyncio.get_running_loop()
    runtime = _PER_LOOP.get(loop)
    if runtime is None:
        router = AsyncWebRouter("nimble", provider_config=_provider_config(config))
        runtime = Runtime(router, asyncio.Semaphore(config.max_in_flight))
        _PER_LOOP[loop] = runtime
    return runtime
