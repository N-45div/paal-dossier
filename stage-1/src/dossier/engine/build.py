"""The evidence strategy of one build (RL1.12, R1.51, R1.131-R1.132).

The skeleton, in order, for one company:

1. one nimble search whose query is the bare normalised domain (``fast``); it is retried
   only after an error answer, never after a timeout;
2. searches for other queries that name the company: nimble first, and tavily only for a
   query that nimble answers with an error;
3. one nimble extract of the best candidate URLs, to read their full served text;
4. one nimble research run asking for the six fields, whose claims count only when their
   citation supports the claimed value.

Every call is preceded by ``gateway.can_call`` for its full table cost, so the build never
reserves more than the budget the gateway enforces.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from .evidence import Evidence
from .providers import ERROR, OK, SKIPPED, Answer, Claim, Gateway, Page
from .result import FIELD_NAMES, BuildResult

NIMBLE = "nimble"
TAVILY = "tavily"
SEARCH_DEPTH = "fast"
BARE_SEARCH_ATTEMPTS = 3
TAVILY_FALLBACK_DEPTH = "lite"
MAX_EXTRACT_URLS = 8
EXTRACT_UNIT = 1
RESEARCH_UNITS = 25
# Units of one search, by provider and depth (§9).
SEARCH_UNITS: dict[tuple[str, str], int] = {
    (NIMBLE, "lite"): 1,
    (NIMBLE, "fast"): 5,
    (NIMBLE, "deep"): 15,
    (TAVILY, "lite"): 8,
    (TAVILY, "fast"): 16,
    (TAVILY, "deep"): 16,
}
# Queries that name the company, besides the bare domain (RL1.12 example).
EXTRA_QUERY_TEMPLATES = (
    "{name} headquarters CEO",
    "{name} founded employees",
    "{name} funding raised",
    "{name} legal name registered",
)


def build_fields(domain: str, gateway: Gateway) -> BuildResult:
    """Research ``domain`` through ``gateway`` and decide every field from the evidence."""
    evidence = Evidence(domain)
    pages = _bare_domain_pages(gateway, domain)
    name = _company_name(domain)
    for template in EXTRA_QUERY_TEMPLATES:
        pages.extend(_query_pages(gateway, template.format(name=name)))

    urls = _extract_candidates(domain, pages)
    extracted: list[Page] = []
    if urls and gateway.can_call(EXTRACT_UNIT * len(urls)):
        extracted = _pages_of(gateway.extract(urls))

    # Every served text is evidence (R1.50): a URL may be served with different text by
    # different searches, and each text can support a value on its own.
    for page in pages + extracted:
        evidence.add_page(page)

    if gateway.can_call(RESEARCH_UNITS):
        for claim in _claims_of(gateway.research(domain, list(FIELD_NAMES))):
            evidence.add_claim(claim)

    return BuildResult(
        ok=gateway.any_success,
        spent_units=gateway.spent,
        fields=evidence.decide(),
    )


def _bare_domain_pages(gateway: Gateway, domain: str) -> list[Page]:
    """The one counted search; retried only after an error answer (RL1.12)."""
    answer = Answer(status=ERROR)
    for _ in range(BARE_SEARCH_ATTEMPTS):
        answer = _search(gateway, domain, NIMBLE, SEARCH_DEPTH)
        if answer.status != ERROR:
            break
    return _pages_of(answer)


def _query_pages(gateway: Gateway, query: str) -> list[Page]:
    """Pages for one query that names the company; tavily only after a nimble error."""
    answer = _search(gateway, query, NIMBLE, SEARCH_DEPTH)
    if answer.status == ERROR:
        answer = _search(gateway, query, TAVILY, TAVILY_FALLBACK_DEPTH)
    return _pages_of(answer)


def _search(gateway: Gateway, query: str, provider: str, depth: str) -> Answer:
    """One search, skipped without a call when the gateway cannot afford it."""
    if not gateway.can_call(SEARCH_UNITS[(provider, depth)]):
        return Answer(status=SKIPPED)
    return gateway.search(query, provider, depth)


def _company_name(domain: str) -> str:
    """The company's name as queries write it: first label, '-' read as a space, title case."""
    return domain.split(".", 1)[0].replace("-", " ").title()


def _extract_candidates(domain: str, pages: list[Page]) -> list[str]:
    """Distinct page URLs, the company's own site first, at most MAX_EXTRACT_URLS."""
    own: list[str] = []
    other: list[str] = []
    for url in dict.fromkeys(page.url for page in pages):
        host = urlsplit(url).hostname or ""
        if host == domain or host.endswith("." + domain):
            own.append(url)
        else:
            other.append(url)
    return (own + other)[:MAX_EXTRACT_URLS]


def _pages_of(answer: Answer) -> list[Page]:
    if answer.status != OK:
        return []
    return [item for item in answer.items if isinstance(item, Page)]


def _claims_of(answer: Answer) -> list[Claim]:
    if answer.status != OK:
        return []
    return [item for item in answer.items if isinstance(item, Claim)]
