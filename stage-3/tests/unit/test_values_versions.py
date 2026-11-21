"""Page-version holding rule (stage 3, R3.46): a later gathered version replaces earlier versions
of its URL whose true_from is on or after its own, and ends the latest earlier version it does
not replace on its own true_from. Builder-b, R3B.
"""

from datetime import date, datetime, timezone

from app.records import BuildRecord, PageVersion
from app.values import holding_versions

URL = "https://acme-robotics.test/team"


def _build(index: int, *versions: PageVersion) -> BuildRecord:
    return BuildRecord(index=index, time=datetime(2026, 1, index, tzinfo=timezone.utc),
                       ok=True, spent_units=0, versions=versions)


def _version(true_from: date | None, url: str = URL, candidates: dict | None = None) -> PageVersion:
    return PageVersion(url=url, true_from=true_from, candidates=candidates or {})


def _holding_dates(records: list[BuildRecord], true_at: date) -> list[date | None]:
    return sorted(v.true_from for v in holding_versions(records, true_at) if v.url == URL)


def test_later_version_ends_the_latest_earlier_one_on_its_own_date():
    # Gathered order A (2020), C (2025), B (2022): C is replaced by B, and A stops on 2022.
    records = [_build(1, _version(date(2020, 1, 1))),
               _build(2, _version(date(2025, 1, 1))),
               _build(3, _version(date(2022, 1, 1)))]
    assert _holding_dates(records, date(2021, 1, 1)) == [date(2020, 1, 1)]
    assert _holding_dates(records, date(2023, 1, 1)) == [date(2022, 1, 1)]
    assert _holding_dates(records, date(2026, 1, 1)) == [date(2022, 1, 1)]


def test_version_with_null_true_from_replaces_every_earlier_version_of_its_url():
    records = [_build(1, _version(date(2020, 1, 1))),
               _build(2, _version(date(2024, 1, 1))),
               _build(3, _version(None))]
    assert _holding_dates(records, date(2021, 1, 1)) == []
    assert _holding_dates(records, date(2026, 1, 1)) == []


def test_equal_true_from_replaces_the_earlier_version():
    older = _version(date(2020, 1, 1), candidates={"ceo": ()})
    newer = _version(date(2020, 1, 1), candidates={"ceo": ()})
    records = [_build(1, older), _build(2, newer)]
    holding = [v for v in holding_versions(records, date(2021, 1, 1)) if v.url == URL]
    assert holding == [newer]


def test_gathered_version_with_no_candidates_still_ends_earlier_versions():
    records = [_build(1, _version(date(2020, 1, 1), candidates={"ceo": ()})),
               _build(2, _version(date(2022, 1, 1), candidates={}))]
    assert _holding_dates(records, date(2021, 1, 1)) == [date(2020, 1, 1)]
    assert _holding_dates(records, date(2023, 1, 1)) == [date(2022, 1, 1)]
