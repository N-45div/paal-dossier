"""Page header parsing for stage 2: the `Kind:` and `Published:` lines (R2.5-R2.8).

Kind matches exactly one of own, filing, news, aggregator. Anything else, or no line, takes the
default rule: own when the URL's host is the company's domain, aggregator otherwise.
Published must be a strict RFC 3339 timestamp with an offset; anything else means no time.
"""

from __future__ import annotations

import datetime
import re
from typing import Optional

from .discovery import is_company_host

KINDS = ("own", "filing", "news", "aggregator")

# RFC 3339 date-time: uppercase T and Z (or a numeric offset), no basic forms, no spaces.
_RFC3339 = re.compile(
    r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})"
    r"T(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?:\.\d+)?"
    r"(?P<zone>Z|[+-](?P<off_hour>\d{2}):(?P<off_minute>\d{2}))"
)


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
    """The value unchanged when it is a valid RFC 3339 timestamp with an offset, else None.

    Range-checked: months 1-12, real days, hours 0-23, minutes 0-59, seconds 0-59 (a leap second
    is refused), offsets up to 23:59.
    """
    if value is None:
        return None
    match = _RFC3339.fullmatch(value)
    if match is None:
        return None
    parts = match.groupdict()
    try:
        datetime.date(int(parts["year"]), int(parts["month"]), int(parts["day"]))
    except ValueError:
        return None
    if int(parts["hour"]) > 23 or int(parts["minute"]) > 59 or int(parts["second"]) > 59:
        return None
    if parts["off_hour"] is not None:
        if int(parts["off_hour"]) > 23 or int(parts["off_minute"]) > 59:
            return None
    return value
