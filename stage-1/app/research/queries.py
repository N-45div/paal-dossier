"""Search queries of a build (besides the one that is exactly the domain)."""
from __future__ import annotations

FIELD_WORDS = (
    "legal name registered name legal entity",
    "headquartered in headquarters based in head office",
    "chief executive officer CEO",
    "founded established incorporated",
    "employees employs staff headcount workforce",
    "raised funding invested investment",
    "news announcement",
    "company profile about",
    "directory listing register entity",
    "interview leadership team",
    "press release update report",
    "careers jobs hiring",
)


def variant_queries(domain: str) -> list[str]:
    """Queries naming the company that surface pages stating different fields."""
    return [f"{domain} {words}" for words in FIELD_WORDS]


def sibling_queries(domain: str, titles: list[str], name: str, limit: int) -> list[str]:
    """Queries built from titles of pages already found, to reach pages titled alike.

    ``titles`` is ordered most common first; the company's own name is dropped
    from each so the query keeps the generic wording.
    """
    queries: list[str] = []
    seen: set[str] = set()
    for title in titles:
        words = " ".join(w for w in title.replace(name, " ").split())
        key = words.lower()
        if not words or key in seen:
            continue
        seen.add(key)
        queries.append(f"{domain} {words}")
        if len(queries) == limit:
            break
    return queries
