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
