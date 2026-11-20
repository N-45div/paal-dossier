"""Page header parsing for stage 2: the `Kind:` and `Published:` lines (R2.5-R2.8).

Kind matches exactly one of own, filing, news, aggregator. Anything else, or no line, takes the
default rule: own when the URL's host is the company's domain, aggregator otherwise.
Published must be an RFC 3339 timestamp with an offset (RL66); anything else means no time.
"""

from __future__ import annotations

from typing import Optional

from .discovery import is_company_host
from .timestamps import is_rfc3339

KINDS = ("own", "filing", "news", "aggregator")


def parse_kind(value: Optional[str]) -> Optional[str]:
    """The kind named by a Kind line, or None when the value is not one of KINDS (exact match)."""
    if value in KINDS:
        return value
    return None


def default_kind(url: str, domain: str) -> str:
    """The default-kind rule (R2.8): own on the company's domain, aggregator otherwise."""
    return "own" if is_company_host(url, domain) else "aggregator"


def page_kind(kind_value: Optional[str], url: str, domain: str) -> str:
    """The page's kind: its Kind line when that names one of KINDS, else the default rule."""
    return parse_kind(kind_value) or default_kind(url, domain)


def parse_published(value: Optional[str]) -> Optional[str]:
    """The value as written when it is a valid RFC 3339 timestamp (RL66), else None."""
    return value if is_rfc3339(value) else None
