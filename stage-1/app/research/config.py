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
    second_wave_window: float  # second search wave starts only this early in a build

    @classmethod
    def from_env(cls) -> "Config":
        base_url = os.environ.get("NIMBLE_BASE_URL")
        # unset means the SDK default (live); an empty value counts as set, so it is not live
        live = base_url is None or urlparse(base_url).hostname == LIVE_NIMBLE_HOST
        tavily_url = os.environ.get("TAVILY_BASE_URL") or None
        return cls(
            live=live,
            tavily_enabled=bool(os.environ.get("TAVILY_API_KEY")),
            tavily_base_url=tavily_url,
            call_timeout=45.0 if live else 12.0,
            research_timeout=150.0 if live else 12.0,
            build_deadline=270.0 if live else 25.0,
            second_wave_window=3.0,
        )
