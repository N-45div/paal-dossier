"""The gathering plan of a build: which searches, extracts and research run it makes, within 80 units (L1.21, L1.22).

Plan: one lite Nimble search for the bare domain, four lite searches that name the company otherwise, one Nimble
research run for all six fields, then a Nimble extract of every URL those returned or cited (full text, 1 unit each).
Worst case: 5 searches (5) + research (25) + at most MAX_EXTRACTS extracts (40) = 70 units; if Nimble's domain search
keeps failing, a Tavily lite domain search (8) replaces it, 78 at most. The budget guard in ``ProviderCalls`` refuses
any call that would pass 80. Over the ten sample companies: 43 to 58 units, mean about 47.
"""

from __future__ import annotations

import asyncio

from app.research.pages import ServedText
from app.research.providers import Claim, Gathered, ProviderCalls

SEARCH_ATTEMPTS_FOR_DOMAIN = 4
MAX_EXTRACTS = 40
EXTRACT_CONCURRENCY = 8


def display_name(domain: str) -> str:
    """``acme-robotics.test`` -> ``Acme Robotics``."""
    return " ".join(word.capitalize() for word in domain.split(".")[0].split("-"))


def discovery_queries(domain: str) -> list[str]:
    """Searches besides the bare-domain one; none equals the domain (L1.21)."""
    name = display_name(domain)
    return [
        name,
        f"{name} headquarters chief executive",
        f"{name} founded employees funding",
        f"{domain} legal name registered",
    ]


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
        if result.url not in gathered.search_urls:
            gathered.search_urls.append(result.url)
        text = result.content or result.description
        if text:
            gathered.texts.append(ServedText(result.url, provider, text, complete=False, title=result.title))


async def _search(calls: ProviderCalls, query: str, gathered: Gathered) -> None:
    results, _ = await calls.search(query, "nimble", "lite")
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


def _urls_to_extract(gathered: Gathered, urls: list[str]) -> list[str]:
    fresh = [u for u in dict.fromkeys(urls) if not gathered.has_full_text(u) and u not in gathered.extract_tried]
    chosen = fresh[: max(0, MAX_EXTRACTS - len(gathered.extract_tried))]
    gathered.extract_tried.update(chosen)
    return chosen


async def _extract_all(calls: ProviderCalls, gathered: Gathered, urls: list[str], gate: asyncio.Semaphore) -> None:
    await asyncio.gather(*(_extract(calls, url, gathered, gate) for url in _urls_to_extract(gathered, urls)))


async def gather(calls: ProviderCalls, domain: str) -> Gathered:
    """Searches first, then extracts of what they found while the (slower) research run finishes."""
    gathered = Gathered()
    gate = asyncio.Semaphore(EXTRACT_CONCURRENCY)
    research = asyncio.create_task(_research(calls, domain, gathered))
    await asyncio.gather(
        _domain_search(calls, domain, gathered),
        *(_search(calls, query, gathered) for query in discovery_queries(domain)),
    )
    await _extract_all(calls, gathered, gathered.search_urls, gate)
    await research
    await _extract_all(calls, gathered, [c.url for c in gathered.claims], gate)
    return gathered
