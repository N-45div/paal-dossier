"""The only module that calls providers: WebRouter, in-process, with cost accounting.

Every call reserves its worst-case units from the build's ledger first, then settles
with what it actually cost (see costs.charged_units). Calls never raise to the caller:
a failed call returns None, and the failure is only recorded for the build's result.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from .costs import (
    RENDERED_EXTRACT_COST_PER_URL,
    RESEARCH_START_COST,
    SEARCH_COST,
    charged_units,
)
from .ledger import Ledger

CALL_TIMEOUT_S = 45.0
# A refused call (cost 0) is tried again after this wait: the same call within 1 s of a 429 is refused
# again (stage-2 rate limits). A call that may have reached the provider is never repeated.
REFUSAL_ATTEMPTS = 4  # a refused call is retried until it answers or these attempts run out (RL4)
RETRY_DELAY_S = 1.1
SEARCH_MAX_RESULTS = 10
EXTRACT_FORMAT = "markdown"  # the served text, as the mock serves it for markdown and html
RENDER_OPTIONS = {"render": True}  # RL60: the text the browser shows once the page has loaded

RESEARCH_QUERY = (
    "Research the company {domain} ({name}): its registered legal name, the city of its "
    "headquarters, its chief executive, the year it was founded, its employee headcount, "
    "and its total equity funding raised in US dollars."
)
RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "legal_name": {"type": "string"},
        "hq_city": {"type": "string"},
        "ceo": {"type": "string"},
        "founded_year": {"type": "integer"},
        "headcount_range": {"type": "string"},
        "funding_total": {"type": "integer"},
    },
}


class Gateway:
    def __init__(
        self,
        ledger: Ledger,
        cancelled: Optional[Callable[[], bool]] = None,
        tavily_base_url: Optional[str] = None,
    ) -> None:
        from web_router import WebRouter

        provider_config = {}
        if tavily_base_url:
            provider_config["tavily"] = {"api_base_url": tavily_base_url}
        self._router = WebRouter("nimble", provider_config=provider_config, router=None)
        self._ledger = ledger
        self._cancelled = cancelled
        self._lock = threading.Lock()
        self._answered = 0

    def close(self) -> None:
        self._router.close()

    @property
    def answered_calls(self) -> int:
        with self._lock:
            return self._answered

    def _cancel_requested(self) -> bool:
        return bool(self._cancelled and self._cancelled())

    def _record_answer(self) -> None:
        with self._lock:
            self._answered += 1

    def _call_with_retry(self, units: int, call: Callable[[], object]):
        """Make the call; a refusal (cost 0) is retried after RETRY_DELAY_S. The caller holds the
        reservation. Returns (answer, units charged). A failure that may have reached the
        provider is charged in full and not repeated."""
        charged = 0
        for attempt in range(REFUSAL_ATTEMPTS):
            if attempt:
                time.sleep(RETRY_DELAY_S)
            if self._cancel_requested():
                break
            try:
                answer = call()
            except Exception as error:  # every provider failure is an outcome, never a crash
                cost = charged_units(error, units)
                charged += cost
                if cost:
                    break
                continue
            charged += units
            self._record_answer()
            return answer, charged
        return None, charged

    def _run(self, units: int, call: Callable[[], object]):
        """Reserve, call (with the refusal retry), settle. Returns the answer, or None."""
        if self._cancel_requested() or not self._ledger.reserve(units):
            return None
        answer, charged = self._call_with_retry(units, call)
        self._ledger.settle(units, charged)
        return answer

    def search(self, provider: str, query: str, depth: str = "lite"):
        """One search. Returns the response, or None when it was not sent or failed."""
        units = SEARCH_COST[(provider, depth)]
        return self._run(
            units,
            lambda: self._router.search(
                query,
                provider=provider,
                max_results=SEARCH_MAX_RESULTS,
                search_depth=depth,
                timeout=CALL_TIMEOUT_S,
                data_apis=False,
            ),
        )

    def reserve_extract(self) -> bool:
        """Reserve the cost of one rendered extract. Settle via extract_reserved."""
        return self._ledger.reserve(RENDERED_EXTRACT_COST_PER_URL["nimble"])

    def extract_reserved(self, url: str):
        """Extract a URL's rendered text, whose cost the caller has already reserved. Settles the reservation."""
        units = RENDERED_EXTRACT_COST_PER_URL["nimble"]
        if self._cancel_requested():
            self._ledger.settle(units, 0)
            return None

        def once():
            response = self._router.extract(
                url,
                provider="nimble",
                format=EXTRACT_FORMAT,
                provider_options=RENDER_OPTIONS,
                timeout=CALL_TIMEOUT_S,
                data_apis=False,
            )
            return response.documents[0] if response.documents else None

        document, charged = self._call_with_retry(units, once)
        self._ledger.settle(units, charged)
        return document

    def start_research(self, domain: str, name: str):
        """Start the nimble research run for all six fields. Returns the job, or None."""
        units = RESEARCH_START_COST["nimble"]
        query = RESEARCH_QUERY.format(domain=domain, name=name)
        return self._run(
            units,
            lambda: self._router.submit_research(
                query, provider="nimble", output_schema=RESEARCH_SCHEMA
            ),
        )

    def await_research(self, job, deadline: float):
        """Wait for a started run until the deadline. Polling is free. Returns None on failure."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            answer = job.result(timeout=remaining)
        except Exception:
            return None
        self._record_answer()
        return answer
