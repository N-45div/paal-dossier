"""Build records (stage 3, Rul-S3-1): one record per build, the source of truth.

History, the change feed, `as_of` and `values` are derived from these records (see history.py).
A record keeps what a build gathered, page by page; the selected values follow from it by the
selection rule, so nothing derived is stored beside a record."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone

from app.candidates import Candidate
from app.clock import parse_rfc3339


@dataclass
class PageVersion:
    """What one ready build gathered from one URL (Two times per value).

    ``candidates`` maps each field to the candidates this page gave for it; every candidate
    carries this version's ``true_from``. A page with no candidates still has a version."""

    url: str
    true_from: date | None
    candidates: dict[str, tuple[Candidate, ...]] = field(default_factory=dict)


@dataclass
class BuildRecord:
    """A build (§8, Builds): its index in the dossier's build order, its time (the clock time of
    the request that started it), its outcome and spending. A failed build has no versions."""

    index: int
    time: datetime
    ok: bool
    spent_units: int
    versions: tuple[PageVersion, ...] = ()

    @property
    def state(self) -> str:
        return "ready" if self.ok else "failed"

    def candidates(self) -> dict[str, list[Candidate]]:
        """Every candidate of this build, by field, in version order."""
        merged: dict[str, list[Candidate]] = {}
        for version in self.versions:
            for name, found in version.candidates.items():
                merged.setdefault(name, []).extend(found)
        return merged


def default_true_from(published_at: str | None) -> date | None:
    """The date part, in UTC, of a publication time (Two times per value); None without one."""
    if published_at is None:
        return None
    return parse_rfc3339(published_at).astimezone(timezone.utc).date()


def version_for(url: str, true_from: date | None, found: dict[str, list[Candidate]]) -> PageVersion:
    """A page version of one URL: each candidate is stamped with the version's true_from."""
    stamped: dict[str, tuple[Candidate, ...]] = {}
    for name, items in found.items():
        stamped[name] = tuple(replace(candidate, true_from=true_from) for candidate in items)
    return PageVersion(url=url, true_from=true_from, candidates=stamped)


def versions_of(found: dict[str, list[Candidate]], pages: dict[str, date | None]) -> tuple[PageVersion, ...]:
    """Group a build's candidates by URL. ``pages`` lists every gathered URL with its
    true_from; a URL in ``pages`` without candidates still gets an empty version. A candidate
    whose URL is not in ``pages`` takes its true_from from its publication time."""
    by_url: dict[str, dict[str, list[Candidate]]] = {}
    for name, items in found.items():
        for candidate in items:
            by_url.setdefault(candidate.url, {}).setdefault(name, []).append(candidate)
    urls = list(pages) + [url for url in by_url if url not in pages]
    versions = []
    for url in urls:
        if url in pages:
            true_from = pages[url]
        else:
            # Unlisted pages: their candidates' own publication dates decide, uniformly.
            sample = next(iter(by_url[url].values()))[0]
            true_from = default_true_from(sample.published_at)
        versions.append(version_for(url, true_from, by_url.get(url, {})))
    return tuple(versions)

