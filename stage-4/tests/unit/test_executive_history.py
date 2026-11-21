"""Stage 3 executives in history (R3B, R3.28): typed by title, hand-built records."""

from datetime import date, datetime, timezone

from app.candidates import Candidate
from app.history import history
from app.records import BuildRecord, PageVersion

URL = "https://acme-robotics.test/team"


def record(index, day, *members):
    """A ready build whose one page gives the given (title, name, true_from) members."""
    cands = tuple(Candidate(value=name, url=URL, excerpt=f"{name} is the {title}.",
                            provider="nimble", kind="own", title=title, true_from=tf)
                  for title, name, tf in members)
    version = PageVersion(url=URL, true_from=members[0][2] if members else None,
                          candidates={"executives": cands})
    return BuildRecord(index=index, time=datetime(2026, 3, day, tzinfo=timezone.utc), ok=True,
                       spent_units=10, versions=(version,))


def test_first_build_gives_an_initial_entry_for_executives():
    entries = history([record(1, 1, ("cfo", "Ana Silva", date(2025, 9, 1)))])["executives"]
    assert [e.type for e in entries] == ["initial"]


def test_a_changed_name_for_one_title_is_a_change_when_the_new_true_from_is_later():
    records = [record(1, 1, ("cfo", "Ana Silva", date(2025, 9, 1))),
               record(2, 2, ("cfo", "Ana Lima", date(2026, 2, 1)))]
    entries = history(records)["executives"]
    assert [e.type for e in entries] == ["initial", "change"]


def test_a_changed_name_with_an_earlier_or_equal_true_from_is_a_correction():
    records = [record(1, 1, ("cfo", "Ana Silva", date(2025, 9, 1))),
               record(2, 2, ("cfo", "Ana Lima", date(2025, 6, 1)))]
    entries = history(records)["executives"]
    assert [e.type for e in entries] == ["initial", "correction"]
