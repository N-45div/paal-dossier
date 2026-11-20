"""One build (stage 2: RL19, RL60, RL61).

Order of work:
1. Start the nimble research run (25 units) and run the exact-domain search and the five
   support searches together. Each hit keeps the provider that served it.
2. Await the research answer, so its cited URLs take the first render slots.
3. Extract every candidate URL in priority order (RL19) as rendered browser text (RL60, 3 units
   each). Search snippets only order the URLs: they are never evidence (RL60).
4. Read each rendered page into candidates; assert each research claim whose verbatim citation
   is in the rendered text of its page.
5. Decide each field with selection.assemble_field (via Evidence.decide).
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from .discovery import Candidate, Hit, candidates, support_queries
from .evidence import Evidence
from .gateway import Gateway
from .ledger import Ledger
from .support import company_name

GATHER_LIMIT_S = 240.0  # hard stop for gathering and waiting on the research run
EXTRACT_WORKERS = 8  # RL13: the extract pool has at most eight threads
SEARCH_WORKERS = 8  # the research start and the seven searches run in one round


def build(
    domain: str,
    ledger: Ledger,
    retrieved_at: str,
    cancelled: Optional[Callable[[], bool]] = None,
) -> tuple[bool, dict]:
    """Run one build. Returns (ok, fields): ok is True iff some provider call answered.

    fields maps each Dossier field to its assemble_field result, all stamped with retrieved_at.
    """
    deadline = time.monotonic() + GATHER_LIMIT_S
    tavily_url = _tavily_base_url()
    gateway = Gateway(ledger, cancelled=cancelled, tavily_base_url=tavily_url)
    try:
        with ThreadPoolExecutor(SEARCH_WORKERS) as pool:
            job_future = pool.submit(gateway.start_research, domain, company_name(domain).title())
            hits = _search(gateway, domain, tavily_allowed=tavily_url is not None, pool=pool)
            job = job_future.result()
        answer = gateway.await_research(job, deadline) if job is not None else None
        cited = _cited_urls(answer)

        ranked = candidates(hits, domain)
        rendered = _extract_in_priority(gateway, _extraction_order(cited, ranked), deadline)

        evidence = Evidence(domain, retrieved_at)
        for url, document in rendered.items():
            evidence.add_rendered_page(url, document.content)
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


def _search(gateway: Gateway, domain: str, tavily_allowed: bool, pool: ThreadPoolExecutor) -> list[Hit]:
    """Every answered search as hits. Query 0 is the exact-domain search."""
    queries = [domain] + support_queries(domain)
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
                    provider=response.provider,
                )
            )
    return hits


def _domain_search(gateway: Gateway, domain: str, tavily_allowed: bool):
    """The one search whose query is exactly the domain: nimble lite (the gateway retries a
    refusal), then tavily lite when nimble gives no answer."""
    response = gateway.search("nimble", domain, "lite")
    if response is not None:
        return response
    if tavily_allowed:
        return gateway.search("tavily", domain, "lite")
    return None


def _extraction_order(cited: list[str], ranked: list[Candidate]) -> list[str]:
    """RL19: research-cited URLs first, then the candidates in discovery order."""
    return list(dict.fromkeys([*cited, *(candidate.url for candidate in ranked)]))


def _extract_in_priority(gateway: Gateway, urls: list[str], deadline: float) -> dict:
    """Reserve the render cost per URL in priority order, then extract concurrently.

    Reservation happens here, in the calling thread, so the priority order decides which URLs
    get the units. Returns url -> document for the URLs that came back in time.
    """
    futures = {}
    with ThreadPoolExecutor(EXTRACT_WORKERS) as pool:
        for url in urls:
            if time.monotonic() >= deadline or not gateway.reserve_extract():
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
