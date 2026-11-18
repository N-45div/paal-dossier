"""Run-time settings read from the environment (spec section 2) and call limits."""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

BUILD_BUDGET_UNITS = 80
LIVE_NIMBLE_HOST = "sdk.nimbleway.com"


@dataclass(frozen=True)
class Config:
    live: bool
    tavily_enabled: bool
    tavily_base_url: str | None
    call_timeout: float      # one search or extract call
    research_timeout: float  # one research run
    build_deadline: float    # whole build, seconds from its start
    max_in_flight: int       # provider calls at once, across all builds

    @classmethod
    def from_env(cls) -> "Config":
        base_url = os.environ.get("NIMBLE_BASE_URL")
        live = not base_url or urlparse(base_url).hostname == LIVE_NIMBLE_HOST
        tavily_url = os.environ.get("TAVILY_BASE_URL") or None
        return cls(
            live=live,
            tavily_enabled=bool(os.environ.get("TAVILY_API_KEY")),
            tavily_base_url=tavily_url,
            call_timeout=45.0 if live else 4.0,
            research_timeout=150.0 if live else 6.0,
            build_deadline=270.0 if live else 9.0,
            max_in_flight=24,
        )
