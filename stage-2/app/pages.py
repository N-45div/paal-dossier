"""Page kind and publication time, read from a served page's header lines (stage 2, §4).

Rul-S2-3: a `Kind` value is taken only when it is exactly one of the four kinds; otherwise the
kind follows from the URL's host. A `Published` value counts only when it is an RFC 3339
timestamp with an explicit offset (`Z` is an offset); otherwise the page has no publication
time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from app.domain import normalise_domain

KINDS: tuple[str, ...] = ("own", "filing", "news", "aggregator")

_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)


@dataclass(frozen=True)
class PageMeta:
    """The kind of a page and its publication time (RFC 3339 text with its offset, or None)."""

    kind: str
    published_at: str | None


def page_meta(headers: dict[str, str], url: str, company_domain: str) -> PageMeta:
    """Kind and publication time of the page served at ``url`` with these header lines."""
    return PageMeta(
        kind=_kind(headers.get("Kind"), url, company_domain),
        published_at=_published(headers.get("Published")),
    )


def _kind(declared: str | None, url: str, company_domain: str) -> str:
    if declared in KINDS:
        return declared
    host = normalise_domain(urlsplit(url).hostname or "")
    return "own" if host is not None and host == company_domain else "aggregator"


def _published(value: str | None) -> str | None:
    """The timestamp as its own offset isoformat, or None when it is not RFC 3339 with offset."""
    if value is None or _RFC3339.match(value) is None:
        return None
    text = value.strip()
    if text[-1] in "Zz":
        text = text[:-1] + "+00:00"
    text = text[:10] + "T" + text[11:]  # date and time joined by T, whatever separator was written
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.isoformat()
