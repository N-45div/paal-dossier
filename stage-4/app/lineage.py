"""Lineage header lines of a served page (stage 4, §4 Pages, R4.5-R4.11).

`Registrant: <domain>` names the domain whose owner publishes the page. `Canonical: <URL>` says the
page is a copy of the URL. `First-Published-By: <domain>` says the page republishes material first
published by that domain. Domains and the host of a Canonical URL are normalised as in §4. A page
with no valid Registrant line has the host of its own URL as its registrant.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from app.domain import normalise_domain


def host_of(url: str) -> str | None:
    """The normalised host of a URL, or None when it has no valid host."""
    try:
        hostname = urlsplit(url).hostname
    except ValueError:
        return None
    return normalise_domain(hostname) if hostname else None


def _canonical_url(text: str | None) -> str | None:
    """A Canonical line's URL when it is an http or https URL with a valid host; else None."""
    if text is None:
        return None
    value = text.strip()
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or host_of(value) is None:
        return None
    return value


@dataclass(frozen=True)
class Lineage:
    """A page's lineage: its registrant (normalised; the host of its own URL when no valid
    Registrant line), the Canonical URL it copies (or None), and the domain it republishes for
    (First-Published-By, normalised, or None)."""

    registrant: str | None
    canonical: str | None
    first_published_by: str | None


def lineage_of(headers: dict[str, str], url: str) -> Lineage:
    registrant = normalise_domain(headers.get("Registrant", "") or "") or host_of(url)
    first = headers.get("First-Published-By")
    return Lineage(
        registrant=registrant,
        canonical=_canonical_url(headers.get("Canonical")),
        first_published_by=normalise_domain(first) if first is not None else None,
    )


def is_lookalike(declared_kind: str | None, lineage: Lineage, url: str) -> bool:
    """R4.11: a page that states `Kind: own` and whose registrant is not the host of its own URL."""
    return declared_kind == "own" and lineage.registrant != host_of(url)
