"""One research build: search, gather, research, then decide every field (stage-1.md sections 8 and 9)."""

import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field

from web_router import WebRouter

from .budget import EXTRACT_UNITS_PER_URL, RESEARCH_UNITS, SEARCH_UNITS, Budget
from .calls import UNANSWERED, perform
from .evidence import decide_fields, evidence_from_pages
from .nimble import NimbleProvider
from .outcome import BuildOutcome, failed_outcome

DEADLINE_S = 280.0  # a build ends `ready` or `failed` within this many seconds (G12)
POOL_WORKERS = 8
RESEARCH_QUERY = (
    "Research {domain}: legal name, headquarters city, CEO, founding year, headcount and total equity funding."
)
# Searches other than the domain search: each names the company with different words.
NAME_QUERY_SUFFIXES = ("", " CEO", " headquarters", " founded", " employees", " funding", " legal name", " news", " investors", " company profile")


def company_name(domain: str) -> str:
    """The first label of the domain with each '-' read as a space, capitalised."""
    return " ".join(part.capitalize() for part in domain.split(".", 1)[0].split("-"))


@dataclass
class _Gathered:
    any_answered: bool = False
    pages: list[tuple[str, str]] = field(default_factory=list)


def run_build(domain: str) -> BuildOutcome:
    """Research one company through Nimble and return its outcome. Never raises."""
    budget = Budget()
    try:
        provider = NimbleProvider(WebRouter("nimble"))
        return _build(domain, provider, budget, time.monotonic() + DEADLINE_S)
    except Exception:  # noqa: BLE001 - the contract is never to raise
        return failed_outcome(spent_units=budget.spent)


def _build(domain: str, provider: NimbleProvider, budget: Budget, deadline_at: float) -> BuildOutcome:
    pool = ThreadPoolExecutor(max_workers=POOL_WORKERS)
    try:
        searches, research = _phase_search(domain, provider, budget, pool, deadline_at)
        gathered = _phase_gather(domain, provider, budget, pool, deadline_at, searches, research)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    answered_any = (
        gathered.any_answered or research.answered or any(outcome.answered for outcome in searches.values())
    )
    evidence = evidence_from_pages(domain, gathered.pages)
    return BuildOutcome(ok=answered_any, fields=decide_fields(evidence), spent_units=budget.spent)


def _phase_search(domain, provider, budget, pool, deadline_at):
    """The domain search, the name searches and the research run, all at once."""
    queries = {domain: "domain"} | {f"{company_name(domain)}{suffix}": "name" for suffix in NAME_QUERY_SUFFIXES}
    futures = {}
    for query in queries:
        futures[query] = pool.submit(perform, budget, SEARCH_UNITS, lambda q=query: provider.search(q))
    research_query = RESEARCH_QUERY.format(domain=domain)
    research_future = pool.submit(
        perform, budget, RESEARCH_UNITS, lambda: provider.research(research_query), attempts=4
    )
    searches = _collect(futures, deadline_at)
    research = _collect({"research": research_future}, deadline_at)["research"]
    return searches, research


def _phase_gather(domain, provider, budget, pool, deadline_at, searches, research):
    """Fetch the full text of every page the answers name, research citations first."""
    urls: list[str] = []
    if research.answered:
        urls.extend(citation.url for citation in research.value)
    urls.extend(url for query, outcome in searches.items() if outcome.answered for url in outcome.value)
    ordered = list(dict.fromkeys(urls))
    futures = {
        url: pool.submit(
            perform, budget, EXTRACT_UNITS_PER_URL, lambda u=url: provider.extract(u)
        )
        for url in ordered
    }
    results = _collect(futures, deadline_at)
    gathered = _Gathered()
    for url in ordered:
        outcome = results[url]
        if outcome.answered:
            gathered.any_answered = True
            if outcome.value is not None:
                gathered.pages.append((url, outcome.value))
    return gathered


def _collect(futures: dict, deadline_at: float) -> dict:
    """Each future's outcome; a call still running at the deadline is unanswered but already charged."""
    wait(list(futures.values()), timeout=max(0.0, deadline_at - time.monotonic()))
    results = {}
    for key, future in futures.items():
        results[key] = future.result() if future.done() else UNANSWERED
    return results
