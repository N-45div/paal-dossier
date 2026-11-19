"""One build: discover pages, extract them, research the six fields, decide (RL4-RL7, RL13).

Order of work: start the research run (25 units), run the exact-domain search and the six
support searches together, extract the ranked URLs while the run works, then read the run's
citations, extract any cited page not yet gathered, and decide each field from the evidence.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from .discovery import rank_urls, support_queries
from .evidence import Evidence
from .gateway import Gateway
from .ledger import Ledger
from .support import company_name

GATHER_LIMIT_S = 240.0  # hard stop for gathering and waiting on the research run
EXTRACT_WORKERS = 8
SEARCH_WORKERS = 4
CITATION_RESERVE_UNITS = 6  # kept free for pages that the research run cites but nothing else found
DOMAIN_SEARCH_ATTEMPTS = 2


def build(
    domain: str,
    ledger: Ledger,
    cancelled: Optional[Callable[[], bool]] = None,
) -> tuple[bool, dict]:
    """Run one build. Returns (ok, fields): ok is True iff some provider call answered."""
    deadline = time.monotonic() + GATHER_LIMIT_S
    tavily_url = _tavily_base_url()
    gateway = Gateway(ledger, cancelled=cancelled, tavily_base_url=tavily_url)
    try:
        evidence = Evidence(domain)
        job = gateway.start_research(domain, company_name(domain).title())
        keep = CITATION_RESERVE_UNITS if job is not None else 0

        hits = _search(gateway, domain, tavily_allowed=tavily_url is not None)
        pages = _extract_all(gateway, rank_urls(hits, domain), keep, deadline)
        for url, document in pages.items():
            evidence.add_page(url, document.content, "nimble")

        if job is not None:
            _take_research(gateway, job, evidence, deadline)

        return gateway.answered_calls > 0, evidence.decide()
    finally:
        gateway.close()


def _tavily_base_url() -> Optional[str]:
    """Tavily is optional: used only when both its key and its base URL are deployed."""
    if os.environ.get("TAVILY_API_KEY") and os.environ.get("TAVILY_BASE_URL"):
        return os.environ["TAVILY_BASE_URL"]
    return None


def _search(gateway: Gateway, domain: str, tavily_allowed: bool) -> list[tuple[str, int]]:
    """Every answered search as (url, rank) hits. The domain search goes first."""
    with ThreadPoolExecutor(SEARCH_WORKERS) as pool:
        domain_future = pool.submit(_domain_search, gateway, domain, tavily_allowed)
        support_futures = [
            pool.submit(gateway.search, "nimble", query) for query in support_queries(domain)
        ]
        responses = [domain_future.result()] + [future.result() for future in support_futures]
    hits: list[tuple[str, int]] = []
    for response in responses:
        if response is None:
            continue
        hits.extend((result.url, rank) for rank, result in enumerate(response.results))
    return hits


def _domain_search(gateway: Gateway, domain: str, tavily_allowed: bool):
    """The one search whose query is exactly the domain: nimble lite, retried, then tavily lite."""
    for _ in range(DOMAIN_SEARCH_ATTEMPTS):
        response = gateway.search("nimble", domain, "lite")
        if response is not None:
            return response
    if tavily_allowed:
        return gateway.search("tavily", domain, "lite")
    return None


def _extract_all(gateway: Gateway, urls: list[str], keep: int, deadline: float) -> dict:
    """Extract URLs concurrently; returns url -> document for those that came back in time."""
    def task(url: str):
        if time.monotonic() >= deadline:
            return None
        return gateway.extract(url, keep=keep)

    with ThreadPoolExecutor(EXTRACT_WORKERS) as pool:
        documents = list(pool.map(task, urls))
    return {url: doc for url, doc in zip(urls, documents) if doc is not None}


def _take_research(gateway: Gateway, job, evidence: Evidence, deadline: float) -> None:
    """Read the run's answer: gather each cited page, then assert the claims it supports."""
    answer = gateway.await_research(job, deadline)
    if answer is None or not answer.structured or not isinstance(answer.structured, dict):
        return
    citations = [c for c in (answer.citations or []) if (c.field or "").startswith("$.")]
    missing = list(dict.fromkeys(c.url for c in citations if c.url not in evidence.pages))
    for url, document in _extract_all(gateway, missing, 0, deadline).items():
        evidence.add_page(url, document.content, "nimble")
    for citation in citations:
        field = citation.field[2:]
        claimed = answer.structured.get(field)
        if claimed is not None:
            evidence.add_research_claim(citation.url, field, claimed, citation.snippet or "")
