"""Stage 3 build records from a build's candidates (Rul-S3-1), hand-built, no store."""

from datetime import date, datetime, timezone

from app.build_records import build_record, field_snapshots
from app.candidates import Candidate
from app.support import FIELDS

T = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
URL = "https://acme-robotics.test/about"


def cand(field, value, url=URL, **kw):
    return Candidate(value=value, url=url, excerpt=f"{value}.", provider="nimble", kind="own",
                     field=field, **kw)


def test_seven_fields_with_executives_last_and_status():
    snaps = field_snapshots({"ceo": [cand("ceo", "Dana Ruiz")],
                             "executives": [cand("executives", "Ana Silva", title="cfo")]})
    assert list(snaps) == [*FIELDS, "executives"]
    assert snaps["ceo"].value == "Dana Ruiz" and snaps["ceo"].status == "known"
    assert snaps["hq_city"].status == "unknown" and snaps["hq_city"].value is None
    assert snaps["executives"].value == [{"title": "cfo", "name": "Ana Silva"}]


def test_record_has_a_version_for_every_gathered_url_even_without_candidates():
    other = "https://news.test/a"
    record = build_record(1, T, True, 34, {"ceo": [cand("ceo", "Dana Ruiz")]},
                          [(URL, date(2025, 9, 1)), (other, None)])
    assert [v.url for v in record.versions] == [URL, other]
    assert record.versions[0].true_from == date(2025, 9, 1)
    assert len(record.versions[1].candidates) == 0
    assert record.fields["ceo"].value == "Dana Ruiz"


def test_failed_build_keeps_spending_and_nothing_else():
    record = build_record(2, T, False, 5, {"ceo": [cand("ceo", "Dana Ruiz")]}, [(URL, None)])
    assert record.ok is False and record.spent_units == 5
    assert record.versions == () and record.fields == {}


def test_each_gathered_url_is_listed_once():
    record = build_record(1, T, True, 10, {}, [(URL, None), (URL, None)])
    assert len(record.versions) == 1
