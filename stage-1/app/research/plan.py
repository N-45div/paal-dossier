"""The gathering plan of a build: which searches, extracts and research run it makes, within 80 units (L1.21, L1.22).

Plan: one lite Nimble search for the bare domain, fourteen lite searches pairing the domain, and the company name, with each
field's statement phrases, and one Nimble research run for all six fields. Then Nimble extracts (full text, 1 unit each) of
the URLs the searches returned, most-returned first, keeping CLAIM_EXTRACT_RESERVE units back for the pages the research
run cites, which are extracted last.
Worst case: 15 searches (15) + research (25) + at most MAX_EXTRACTS extracts (40) = 80 units; if Nimble's domain search
keeps failing, a Tavily lite domain search (8) replaces it. The budget guard in ``ProviderCalls`` refuses any call that
would pass 80. Over the sample corpus: 53 to 71 units. On variant corpora (other seed, noise 0.5, rate_limit 0.3, weather
on, decoy pages, no own about page): at most 75 units.
"""

from __future__ import annotations

import asyncio

from app.research.pages import ServedText
from app.research.providers import UNITS_PER_BUILD, Gathered, ProviderCalls

SEARCH_ATTEMPTS_FOR_DOMAIN = 4
CALL_ATTEMPTS = 3
CLAIM_EXTRACT_RESERVE = 6  # units kept back so research-cited pages can still be fetched
MAX_EXTRACTS = 40
EXTRACT_CONCURRENCY = 20


def display_name(domain: str) -> str:
    """``acme-robotics.test`` -> ``Acme Robotics``."""
    return " ".join(word.capitalize() for word in domain.split(".")[0].split("-"))


FIELD_QUERY_TERMS = (
    "legal name registered name",
    "headquartered in based in",
    "chief executive officer CEO",
    "founded established incorporated",
    "employees staff headcount",
    "raised funding investment",
)


def discovery_queries(domain: str) -> list[str]:
    """Searches besides the bare-domain one: the domain and name beside each field's statement phrases.

    Naming the domain keeps the company's own pages ahead of pages that merely mention it.
    """
    name = display_name(domain)
    by_domain = [f"{domain} {name}", *(f"{domain} {name} {terms}" for terms in FIELD_QUERY_TERMS)]
    by_name = [name, *(f"{name} {terms}" for terms in FIELD_QUERY_TERMS)]
    return by_domain + by_name


async def _domain_search(calls: ProviderCalls, domain: str, gathered: Gathered) -> None:
    """The one search whose query is exactly the domain; retried only while it errors."""
    results, outcome = await calls.search(domain, "nimble", "lite", attempts=SEARCH_ATTEMPTS_FOR_DOMAIN)
    if results is None and calls.tavily_enabled and not outcome.ok and outcome.cost == 0:
        results, outcome = await calls.search(domain, "tavily", "lite", attempts=2)
    if results is not None:
        gathered.domain_searched = True
        _record_results(gathered, results, "nimble" if outcome.cost <= 1 else "tavily")


def _record_results(gathered: Gathered, results: list, provider: str) -> None:
    gathered.successes += 1
    for result in results:
        gathered.url_hits[result.url] = gathered.url_hits.get(result.url, 0) + 1
        if result.url not in gathered.search_urls:
            gathered.search_urls.append(result.url)
        text = result.content or result.description
        if text:
            gathered.texts.append(ServedText(result.url, provider, text, complete=False, title=result.title))


async def _search(calls: ProviderCalls, query: str, gathered: Gathered) -> None:
    results, _ = await calls.search(query, "nimble", "lite", attempts=CALL_ATTEMPTS)
    if results is not None:
        _record_results(gathered, results, "nimble")


async def _research(calls: ProviderCalls, domain: str, gathered: Gathered) -> None:
    claims, outcome = await calls.research(domain)
    if outcome.ok:
        gathered.successes += 1
        gathered.claims.extend(claims)


async def _extract(calls: ProviderCalls, url: str, gathered: Gathered, gate: asyncio.Semaphore) -> None:
    async with gate:
        content, _ = await calls.extract(url)
    if content:
        gathered.successes += 1
        gathered.texts.append(ServedText(url, "nimble", content, complete=True))


def _urls_to_extract(gathered: Gathered, urls: list[str], limit: int) -> list[str]:
    fresh = [u for u in dict.fromkeys(urls) if not gathered.has_full_text(u) and u not in gathered.extract_tried]
    chosen = fresh[: max(0, min(limit, MAX_EXTRACTS - len(gathered.extract_tried)))]
    gathered.extract_tried.update(chosen)
    return chosen


async def _extract_all(
    calls: ProviderCalls, gathered: Gathered, urls: list[str], gate: asyncio.Semaphore, limit: int
) -> None:
    chosen = _urls_to_extract(gathered, urls, limit)
    await _settled(*(_extract(calls, url, gathered, gate) for url in chosen))


async def _settled(*coroutines) -> None:
    """Run every coroutine to completion; one failing never leaves another call in flight (L1.27)."""
    await asyncio.gather(*coroutines, return_exceptions=True)


async def gather(calls: ProviderCalls, domain: str) -> Gathered:
    """Searches first, then extracts of what they found while the (slower) research run finishes.

    Every call issued is awaited before this returns, so every one is accounted for in the build's spending.
    """
    gathered = Gathered()
    gate = asyncio.Semaphore(EXTRACT_CONCURRENCY)
    research = asyncio.create_task(_research(calls, domain, gathered))
    await _settled(
        _domain_search(calls, domain, gathered),
        *(_search(calls, query, gathered) for query in discovery_queries(domain)),
    )
    by_yield = sorted(gathered.search_urls, key=lambda u: -gathered.url_hits[u])  # stable: first found wins ties
    room = UNITS_PER_BUILD - calls.committed - CLAIM_EXTRACT_RESERVE
    await _extract_all(calls, gathered, by_yield, gate, room)
    await _settled(research)
    await _extract_all(calls, gathered, [c.url for c in gathered.claims], gate, MAX_EXTRACTS)
    return gathered
