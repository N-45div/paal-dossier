"""Binds the build orchestrator to the research engine (ruling L1.01)."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

RunBuild = Callable[[str, Callable[[int], None]], Awaitable[dict[str, Any]]]

try:
    from .research import run_build as run_build
except ImportError:  # the research engine has not landed yet

    async def run_build(domain: str, spend: Callable[[int], None]) -> dict[str, Any]:
        """Placeholder engine: researches nothing and finds nothing."""
        return {"ok": True, "fields": {}}
