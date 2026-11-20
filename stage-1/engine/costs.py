"""Unit prices of provider calls (spec §9) and the rule for what an attempt costs (RL5)."""

from __future__ import annotations

SEARCH_COST = {
    ("nimble", "lite"): 1,
    ("nimble", "fast"): 5,
    ("nimble", "deep"): 15,
    ("tavily", "lite"): 8,
    ("tavily", "fast"): 16,
    ("tavily", "deep"): 16,
}
EXTRACT_COST_PER_URL = {"nimble": 1, "tavily": 2}
RESEARCH_START_COST = {"nimble": 25}


PAGE_LEVEL_KINDS = ("target", "not_found")
# Kinds that only an HTTP error status produces (types_errors.py). Some SDKs omit the status
# code, so the kind is the evidence that the provider refused the call (429 rate_limit: tavily).
REFUSAL_KINDS = ("rate_limit", "auth", "bad_request", "not_found")


def charged_units(error: BaseException, units: int) -> int:
    """Units a call that raised ``error`` still costs.

    A call refused with an error status costs nothing, whatever SDK raised it: the HTTP status
    is read from the error and its cause (web_router's classify). A call that was never sent
    costs nothing. Any other failure (timeout, connection failure, unreadable answer) may have
    reached the provider, so it costs its full price.
    """
    from web_router import (  # imported here so that support.py stays dependency-free
        ConfigurationError,
        ExtractFailedError,
        InvalidParameterError,
        MissingParameterError,
        ProviderNotFoundError,
        UnsupportedFormatError,
        UnsupportedParameterError,
    )
    from web_router.types_errors import classify

    not_sent = (
        ConfigurationError,
        InvalidParameterError,
        MissingParameterError,
        ProviderNotFoundError,
        UnsupportedFormatError,
        UnsupportedParameterError,
    )
    if isinstance(error, not_sent):
        return 0
    if isinstance(error, ExtractFailedError) and error.kind in PAGE_LEVEL_KINDS:
        return units  # the provider answered that no page exists here: not a refusal
    facts = classify(error, str(error))
    if facts.status_code is not None or facts.kind in REFUSAL_KINDS:
        return 0  # an HTTP error status or a refused key or throttle: the provider refused the call
    return units
