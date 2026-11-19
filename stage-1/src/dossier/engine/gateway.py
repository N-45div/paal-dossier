"""The only code that calls a provider. Every call goes through WebRouter (spec 2, R1.10).

Budget (R1.127-R1.131): a call reserves its table cost before it is sent. When the provider
answers with an error status, the reserve is given back. A call that gets no answer (timeout,
connection failure, unreadable answer) keeps its reserve. An extract URL answered with no page
(404) costs its unit: only other error statuses refuse a URL.

Calls are synchronous. Reserving, refunding and the counters are under one lock, so several
threads may call the gateway at once. Every call has a timeout of at least 30 s and never sets
`render`. Search results are capped at 10.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from web_router import ConfigurationError, ResearchTimeoutError, WebRouter

from .providers import ERROR, OK, SKIPPED, TIMEOUT, Answer, Claim, Page

FIELD_NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")
_FIELD_TYPES = {"founded_year": "integer", "funding_total": "integer"}

# Cost table, spec section 9 (units).
SEARCH_COST = {
    ("nimble", "lite"): 1,
    ("nimble", "fast"): 5,
    ("nimble", "deep"): 15,
    ("tavily", "lite"): 8,
    ("tavily", "fast"): 16,
    ("tavily", "deep"): 16,
}
EXTRACT_UNIT = 1  # nimble, per URL requested
RESEARCH_UNITS = 25  # nimble, when the run is started

MAX_RESULTS = 10
CALL_TIMEOUT_S = 30.0  # per call, the least the live providers are allowed
SEARCH_ADMIT_S = 30.0  # time left needed before a search or extract may start
RESEARCH_ADMIT_S = 60.0  # time left needed before a research run may start
DEFAULT_DEADLINE_S = 280.0  # hard cap per build (RL1.12)


class Gateway:
    """Budgeted access to the providers for one build. Use as a context manager, or close()."""

    def __init__(
        self,
        budget: int = 80,
        deadline_s: float = DEFAULT_DEADLINE_S,
        cancel: threading.Event | None = None,
        router: Any = None,
    ) -> None:
        self.budget = budget
        self.deadline_s = deadline_s
        self.cancel = cancel
        self.spent = 0
        self.any_success = False
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self._router = router if router is not None else _new_router()

    def __enter__(self) -> Gateway:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        close = getattr(self._router, "close", None)
        if close is not None:
            close()

    def can_call(self, units: int) -> bool:
        """Advisory: would a call of `units` be admitted now? The call itself reserves."""
        with self._lock:
            return self._fits(units, SEARCH_ADMIT_S)

    def search(self, query: str, provider: str, depth: str) -> Answer:
        cost = SEARCH_COST.get((provider, depth))
        if cost is None or not self._admit(cost, SEARCH_ADMIT_S):
            return Answer(status=SKIPPED)
        try:
            response = self._router.search(
                query, provider=provider, search_depth=depth, max_results=MAX_RESULTS
            )
        except Exception as error:
            return self._failed(error, cost)
        pages = tuple(
            Page(result.url, result.title, result.content or result.description, provider)
            for result in response.results[:MAX_RESULTS]
        )
        return self._answered(pages)

    def extract(self, urls: list[str]) -> Answer:
        urls = list(dict.fromkeys(urls))
        cost = EXTRACT_UNIT * len(urls)
        if not urls or not self._admit(cost, SEARCH_ADMIT_S):
            return Answer(status=SKIPPED)
        try:
            response = self._router.extract(urls, provider="nimble")
        except Exception as error:
            failures = getattr(error, "url_failures", None)
            if failures is None:
                return self._failed(error, cost)
            return self._extracted((), {f.url for f in failures if _is_refusal(f.status_code, True)}, urls)
        refused = {f.url for f in response.failures if _is_refusal(f.status_code, True)}
        pages = tuple(
            Page(document.url, document.title, document.content, "nimble") for document in response.documents
        )
        return self._extracted(pages, refused - {page.url for page in pages}, urls)

    def research(self, domain: str, fields: list[str]) -> Answer:
        if not self._admit(RESEARCH_UNITS, RESEARCH_ADMIT_S):
            return Answer(status=SKIPPED)
        try:
            response = self._router.research(
                _research_query(domain),
                provider="nimble",
                output_schema=_schema(fields),
                timeout=self.deadline_s - self._elapsed(),
            )
        except ResearchTimeoutError:
            return Answer(status=TIMEOUT)  # the run keeps going, so its cost stands
        except Exception as error:
            return self._failed(error, RESEARCH_UNITS)
        return self._answered(_claims(response, fields))

    def _fits(self, units: int, needed_s: float) -> bool:
        if self.cancel is not None and self.cancel.is_set():
            return False
        if self._elapsed() + needed_s > self.deadline_s:
            return False
        return self.spent + units <= self.budget

    def _admit(self, units: int, needed_s: float) -> bool:
        with self._lock:
            if not self._fits(units, needed_s):
                return False
            self.spent += units
            return True

    def _refund(self, units: int) -> None:
        with self._lock:
            self.spent -= units

    def _elapsed(self) -> float:
        return time.monotonic() - self._started

    def _answered(self, items: tuple) -> Answer:
        with self._lock:
            self.any_success = True
        return Answer(status=OK, items=items)

    def _failed(self, error: BaseException, units: int) -> Answer:
        if isinstance(error, ConfigurationError):
            self._refund(units)  # no credential: the request was never sent, so nothing is charged
            return Answer(status=SKIPPED)
        if _is_refusal(_status_of(error), extract=False):
            self._refund(units)
            return Answer(status=ERROR)
        return Answer(status=TIMEOUT)

    def _extracted(self, pages: tuple, refused: set[str], urls: list[str]) -> Answer:
        refunded = [url for url in urls if url in refused]
        if refunded:
            self._refund(EXTRACT_UNIT * len(refunded))
        if len(refunded) == len(urls):
            return Answer(status=ERROR)
        return self._answered(pages)


def _is_refusal(status: int | None, extract: bool) -> bool:
    """An error status refuses the call. For extract, 404 is a missing page and costs its unit."""
    if status is None or status < 400:
        return False
    return not (extract and status == 404)


def _status_of(error: BaseException) -> int | None:
    """The HTTP status of an error or of the error it wraps, when one is recorded."""
    current: BaseException | None = error
    for _ in range(10):
        if current is None:
            return None
        status = getattr(current, "status_code", None)
        if isinstance(status, int):
            return status
        current = current.__cause__ or current.__context__
    return None


def _schema(fields: list[str]) -> dict:
    names = [name for name in FIELD_NAMES if name in fields]
    return {
        "type": "object",
        "properties": {name: {"type": _FIELD_TYPES.get(name, "string")} for name in names},
    }


def _research_query(domain: str) -> str:
    return (
        f"Research the company whose web domain is {domain}: its registered legal name, "
        "headquarters city, chief executive, year founded, headcount range and total equity "
        "funding raised, with the source of each."
    )


def _claims(response: Any, fields: list[str]) -> tuple[Claim, ...]:
    structured = response.structured if isinstance(response.structured, dict) else {}
    claims = []
    for citation in response.citations:
        name = _field_name(citation.field)
        value = structured.get(name) if name else None
        if name in fields and value is not None and citation.snippet:
            claims.append(Claim(name, value, citation.url, citation.snippet, "nimble"))
    return tuple(claims)


def _field_name(path: str | None) -> str | None:
    if not path or not path.startswith("$."):
        return None
    name = path[2:]
    return name if name in FIELD_NAMES else None


def _new_router() -> WebRouter:
    # An empty base URL counts as set and breaks every call (mock README): drop it instead.
    for variable in ("NIMBLE_BASE_URL", "TAVILY_BASE_URL"):
        if os.environ.get(variable) == "":
            del os.environ[variable]
    config: dict[str, dict[str, Any]] = {"nimble": {"timeout": CALL_TIMEOUT_S, "max_retries": 0}}
    if os.environ.get("TAVILY_API_KEY"):
        tavily: dict[str, Any] = {"timeout": CALL_TIMEOUT_S}
        if os.environ.get("TAVILY_BASE_URL"):
            tavily["api_base_url"] = os.environ["TAVILY_BASE_URL"]
        config["tavily"] = tavily
    return WebRouter(provider="nimble", provider_config=config, router=None)
