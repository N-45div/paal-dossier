"""Stage 3 values over build records (R3B, R3.44-R3.53), hand-built records; the executives
per-title rule and page-version replacement."""

from datetime import date, datetime, timezone

from app.candidates import Candidate
from app.evidence import collect_executives
from app.gateway import ServedPage
from app.records import BuildRecord, PageVersion
from app.values import values_at

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
URL = "https://acme-robotics.test/team"


def cand(value, url=URL, title=None):
    return Candidate(value=value, url=url, excerpt=f"{value} is the role.", provider="nimble",
                     kind="own", title=title)


def ready(index, *versions):
    return BuildRecord(index=index, time=T0, ok=True, spent_units=10, versions=tuple(versions))


def version(true_from, field, *candidates, url=URL):
    return PageVersion(url=url, true_from=true_from, candidates={field: tuple(candidates)})


def test_version_holds_from_its_true_from_only():
    records = [ready(1, version(date(2021, 4, 1), "ceo", cand("Dana Ruiz")))]
    assert values_at(records, date(2021, 3, 31))["ceo"].value is None
    assert values_at(records, date(2021, 4, 1))["ceo"].value == "Dana Ruiz"
    assert values_at(records, date(2021, 4, 1))["ceo"].true_from == date(2021, 4, 1)


def test_later_dated_version_of_same_url_ends_the_earlier_one():
    records = [ready(1, version(date(2021, 4, 1), "ceo", cand("Dana Ruiz"))),
               ready(2, version(date(2026, 3, 20), "ceo", cand("Lee Park")))]
    assert values_at(records, date(2025, 6, 1))["ceo"].value == "Dana Ruiz"
    assert values_at(records, date(2026, 4, 1))["ceo"].value == "Lee Park"


def test_earlier_dated_version_replaces_later_one_of_same_url():
    records = [ready(1, version(date(2022, 1, 1), "ceo", cand("Lee Park"))),
               ready(2, version(date(2020, 1, 1), "ceo", cand("Dana Ruiz")))]
    assert values_at(records, date(2023, 1, 1))["ceo"].value == "Dana Ruiz"


def test_null_true_from_replaces_every_earlier_version_of_its_url():
    records = [ready(1, version(date(2021, 4, 1), "ceo", cand("Dana Ruiz"))),
               ready(2, version(None, "ceo", cand("Lee Park")))]
    assert values_at(records, date(2025, 1, 1))["ceo"].value is None


def test_failed_builds_contribute_nothing():
    failed = BuildRecord(index=2, time=T0, ok=False, spent_units=5)
    records = [ready(1, version(date(2021, 4, 1), "ceo", cand("Dana Ruiz"))), failed]
    assert values_at(records, date(2025, 1, 1))["ceo"].value == "Dana Ruiz"


def test_executives_are_per_title_and_seventh_field():
    records = [ready(1, version(date(2025, 9, 1), "executives",
                                cand("Ana Silva", title="cfo"), cand("Ben Okafor", title="cto")))]
    answer = values_at(records, date(2026, 1, 1))["executives"]
    assert answer.value == [{"title": "cfo", "name": "Ana Silva"},
                            {"title": "cto", "name": "Ben Okafor"}]
    assert answer.true_from == date(2025, 9, 1)
    assert len(answer.citations) == 2


def test_executives_unknown_without_titles():
    records = [ready(1, version(date(2025, 9, 1), "ceo", cand("Dana Ruiz")))]
    assert values_at(records, date(2026, 1, 1))["executives"].value is None


def test_collect_executives_one_per_title_name_page_with_true_from():
    page = ServedPage(url=URL, prose="Ana Silva is the chief financial officer of Acme Robotics. "
                                     "Acme Robotics CTO: Ben Okafor. Acme Robotics CTO: Ben Okafor.",
                      headers={"Effective": "2025-09-01", "Kind": "own"})
    found = collect_executives("acme-robotics.test", [page])
    assert sorted((c.title, c.value) for c in found) == [("cfo", "Ana Silva"), ("cto", "Ben Okafor")]
    assert all(c.true_from == date(2025, 9, 1) for c in found)
