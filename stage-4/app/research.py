"""Build strategy for one company: gather pages, then decide its six fields (§8, §9, Rul-9).

``run_build(domain)`` is the contract PA2 calls. Per build:

1. one lite search whose query is exactly the domain (retried until one succeeds), and
   four lite searches naming the company; one Nimble research run asking for all six fields;
2. extract the URLs the searches returned, up to ``EXTRACT_WAVE`` of them;
3. extract the URLs the research citations name that were not gathered yet;
4. decide each field from the gathered prose (``app.evidence``).

Searches and the research run go out together; extraction starts as soon as the searches
answer. Every call is charged to the build's ledger before it is issued, so the build never
spends more than 80 units. A build stops at ``BUILD_DEADLINE_S`` with whatever it has.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from app.budget import BUILD_BUDGET_UNITS, Ledger
from app.evidence import collect_candidates, collect_executives, decide_fields
from app.pages import page_meta
from app.gateway import CitedClaim, NimbleGateway, ServedPage
from app.outcome import BuildOutcome, FieldResult, unknown_fields
from app.support import FIELDS, company_name

__all__ = [
    "FIELD_NAMES",
    "BuildOutcome",
    "FieldResult",
    "run_build",
    "unknown_fields",
]

# Names the dossier layer imports from this module (kept from the placeholder contract).
FIELD_NAMES: tuple[str, ...] = FIELDS

logger = logging.getLogger(__name__)

BUILD_DEADLINE_S = 280.0
EXTRACT_WAVE = 24
EXTRACT_CONCURRENCY = 8
DOMAIN_SEARCH_ATTEMPTS = 3
RETRY_DELAY_S = 1.5

_EXTRA_QUERY_TOPICS = ("headquarters", "chief executive", "founded employees", "funding raised")


def _extra_queries(name: str) -> list[str]:
    return [f"{name} {topic}" for topic in _EXTRA_QUERY_TOPICS]


def _research_query(domain: str) -> str:
    return (
        f"{domain} company profile: legal name, headquarters city, CEO, "
        "founding year, headcount and total funding raised"
    )


def _research_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {name: {"type": "string"} for name in FIELDS}}


class _Gathered:
    """What one build has obtained so far; read after the build ends, even when it was cut short."""

    def __init__(self) -> None:
        self.answered = False
        self.claims: list[CitedClaim] = []
        self.requested: set[str] = set()
        self._pages: dict[tuple[int, int], ServedPage] = {}

    def add_page(self, order: tuple[int, int], page: ServedPage) -> None:
        self._pages[order] = page
        self.answered = True

    def pages_in_order(self) -> list[ServedPage]:
        return [self._pages[key] for key in sorted(self._pages)]


async def run_build(domain: str, on_spend: Callable[[int], None] | None = None) -> BuildOutcome:
    """Research one company by its normalised domain and decide its fields.

    ``on_spend`` (Rul-11) receives each unit change as it happens: ``+units`` when a
    call's cost is reserved, ``-units`` when a refused call's reservation is released.
    The net of those changes equals the returned ``spent_units``.
    """
    ledger = Ledger(BUILD_BUDGET_UNITS)
    gateway = NimbleGateway(ledger, on_spend)
    gathered = _Gathered()
    if not gateway.available:  # nothing can be called: fail at once, spend nothing
        logger.error("no Nimble client for build of %s", domain)
        return _failed(0)
    try:
        async with asyncio.timeout(BUILD_DEADLINE_S):
            await _gather(domain, gateway, gathered)
    except TimeoutError:
        logger.warning("build for %s reached its deadline", domain)
    except Exception:  # a bug must end this build as failed, never crash the service
        logger.exception("build for %s failed", domain)
    if not gathered.answered:
        return _failed(ledger.spent)
    pages = gathered.pages_in_order()
    candidates = collect_candidates(domain, pages)
    candidates["executives"] = collect_executives(domain, pages)
    return BuildOutcome(
        ok=True,
        spent_units=ledger.spent,
        fields=decide_fields(candidates),
        candidates=candidates,
        pages={page.url: page_meta(page.headers, page.url, domain).true_from for page in pages},
    )


def _failed(spent_units: int) -> BuildOutcome:
    return BuildOutcome(
        ok=False,
        spent_units=spent_units,
        fields=unknown_fields(),
        candidates={name: [] for name in FIELD_NAMES},
    )


async def _gather(domain: str, gateway: NimbleGateway, gathered: _Gathered) -> None:
    research = asyncio.ensure_future(_research(domain, gateway, gathered))
    try:
        search_urls = await _search(domain, gateway, gathered)
        await _extract(search_urls, phase=0, gateway=gateway, gathered=gathered)
        await research
        cited = [claim.url for claim in gathered.claims if claim.url not in gathered.requested]
        await _extract(list(dict.fromkeys(cited)), phase=1, gateway=gateway, gathered=gathered)
    finally:
        research.cancel()


async def _research(domain: str, gateway: NimbleGateway, gathered: _Gathered) -> None:
    claims, _ = await gateway.research(_research_query(domain), _research_schema())
    if claims is not None:
        gathered.claims = claims
        gathered.answered = True


async def _search(domain: str, gateway: NimbleGateway, gathered: _Gathered) -> list[str]:
    """The domain search (retried until it succeeds) with the extra searches, URLs in order."""
    name = company_name(domain)
    results = await asyncio.gather(
        _domain_search(domain, gateway),
        *(_single_search(query, gateway) for query in _extra_queries(name)),
    )
    if any(urls is not None for urls in results):
        gathered.answered = True
    ordered: list[str] = []
    for urls in results:
        ordered.extend(urls or [])
    return list(dict.fromkeys(ordered))[:EXTRACT_WAVE]


async def _domain_search(domain: str, gateway: NimbleGateway) -> list[str] | None:
    for _ in range(DOMAIN_SEARCH_ATTEMPTS):
        urls = await _single_search(domain, gateway)
        if urls is not None:
            return urls
        await asyncio.sleep(RETRY_DELAY_S)
    return None


async def _single_search(query: str, gateway: NimbleGateway) -> list[str] | None:
    urls, _ = await gateway.search(query)
    return urls


async def _extract(urls: list[str], phase: int, gateway: NimbleGateway, gathered: _Gathered) -> None:
    gathered.requested.update(urls)
    semaphore = asyncio.Semaphore(EXTRACT_CONCURRENCY)

    async def one(index: int, url: str) -> None:
        async with semaphore:
            page, refused = await gateway.extract(url)
            if refused:
                await asyncio.sleep(RETRY_DELAY_S)
                page, _ = await gateway.extract(url)
        if page is not None:
            gathered.add_page((phase, index), page)

    await asyncio.gather(*(one(index, url) for index, url in enumerate(urls)))
