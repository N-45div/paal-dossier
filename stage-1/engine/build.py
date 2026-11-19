"""One build (RL4-RL7, RL13, RL14, RL19).

Order of work:
1. Start the nimble research run (25 units).
2. Run the exact-domain search and the six support searches together.
3. Free text: a lite snippet already held is page text. A snippet shorter than 300 characters
   is the whole prose, so its URL is not extracted. A longer snippet gives its complete sentences.
4. Extract the remaining candidates in priority order (RL19), keeping the research reserve free.
5. Read the research answer; extract cited URLs not held in full (reserve units) and assert
   only the claims whose verbatim citation supports the claimed value.
6. Decide each field from the gathered pages.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from .discovery import Hit, candidates, support_queries
from .evidence import Evidence
from .gateway import Gateway
from .ledger import Ledger
from .support import complete_sentences_prefix, company_name

GATHER_LIMIT_S = 240.0  # hard stop for gathering and waiting on the research run
EXTRACT_WORKERS = 8
SEARCH_WORKERS = 4
CITATION_RESERVE_UNITS = 6  # kept for the research run's cited pages (one per field)
DOMAIN_SEARCH_ATTEMPTS = 2
SNIPPET_CHARS = 300  # the lite snippet length: a shorter one is the whole prose


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
        job = gateway.start_research(domain, company_name(domain).title())
        keep = CITATION_RESERVE_UNITS if job is not None else 0

        hits = _search(gateway, domain, tavily_allowed=tavily_url is not None)
        ranked = candidates(hits, domain)

        free_pages, partial_pages = _free_text(ranked)
        fetched = _extract_in_priority(
            gateway, [c.url for c in ranked if c.url not in free_pages], keep, deadline
        )

        answer = gateway.await_research(job, deadline) if job is not None else None
        cited = _cited_urls(answer)
        missing = [u for u in cited if u not in fetched and u not in free_pages]
        fetched.update(_extract_in_priority(gateway, missing, 0, deadline))

        evidence = Evidence(domain)
        searched = {c.url for c in ranked}  # RL21: pages a search of this build returned
        for url in [c.url for c in ranked]:
            if url in fetched:
                evidence.add_served_text(url, fetched[url].content, "nimble", searched=True)
            elif url in free_pages:
                evidence.add_prose(url, free_pages[url], "nimble", searched=True)
            elif url in partial_pages:
                evidence.add_prose(url, partial_pages[url], "nimble", searched=True)
        for url in cited:
            if url in fetched and url not in evidence.pages:
                evidence.add_served_text(url, fetched[url].content, "nimble", searched=url in searched)
        if answer is not None:
            _assert_research_claims(evidence, answer)

        return gateway.answered_calls > 0, evidence.decide()
    finally:
        gateway.close()


def _tavily_base_url() -> Optional[str]:
    """Tavily is optional: used only when both its key and its base URL are deployed."""
    if os.environ.get("TAVILY_API_KEY") and os.environ.get("TAVILY_BASE_URL"):
        return os.environ["TAVILY_BASE_URL"]
    return None


def _search(gateway: Gateway, domain: str, tavily_allowed: bool) -> list[Hit]:
    """Every answered search as hits. Query 0 is the exact-domain search."""
    queries = [domain] + support_queries(domain)
    with ThreadPoolExecutor(SEARCH_WORKERS) as pool:
        domain_future = pool.submit(_domain_search, gateway, domain, tavily_allowed)
        support_futures = [pool.submit(gateway.search, "nimble", q) for q in queries[1:]]
        responses = [domain_future.result()] + [future.result() for future in support_futures]
    hits: list[Hit] = []
    for query_index, response in enumerate(responses):
        if response is None:
            continue
        for rank, result in enumerate(response.results):
            hits.append(
                Hit(
                    url=result.url,
                    rank=rank,
                    query=query_index,
                    title=result.title or "",
                    snippet=result.description or "",
                )
            )
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


def _free_text(ranked) -> tuple[dict, dict]:
    """Page text already held in search snippets: (whole pages, partial pages by URL)."""
    whole: dict[str, str] = {}
    partial: dict[str, str] = {}
    for candidate in ranked:
        snippet = candidate.snippet
        if not snippet:
            continue
        if len(snippet) < SNIPPET_CHARS:
            whole[candidate.url] = snippet
        else:
            prefix = complete_sentences_prefix(snippet)
            if prefix:
                partial[candidate.url] = prefix
    return whole, partial


def _extract_in_priority(gateway: Gateway, urls: list[str], keep: int, deadline: float) -> dict:
    """Reserve one unit per URL in priority order, then extract concurrently.

    Reservation happens here, in the calling thread, so the priority order decides which URLs
    get the units. Returns url -> document for the URLs that came back in time.
    """
    futures = {}
    with ThreadPoolExecutor(EXTRACT_WORKERS) as pool:
        for url in urls:
            if time.monotonic() >= deadline or not gateway.reserve_extract(keep=keep):
                break
            futures[url] = pool.submit(gateway.extract_reserved, url)
        documents = {url: future.result() for url, future in futures.items()}
    return {url: doc for url, doc in documents.items() if doc is not None}


def _cited_urls(answer) -> list[str]:
    if answer is None or not answer.structured or not isinstance(answer.structured, dict):
        return []
    urls = [c.url for c in (answer.citations or []) if (c.field or "").startswith("$.")]
    return list(dict.fromkeys(urls))


def _assert_research_claims(evidence: Evidence, answer) -> None:
    for citation in answer.citations or []:
        field = (citation.field or "")
        if not field.startswith("$."):
            continue
        field = field[2:]
        claimed = answer.structured.get(field)
        if claimed is not None:
            evidence.add_research_claim(citation.url, field, claimed, citation.snippet or "")
