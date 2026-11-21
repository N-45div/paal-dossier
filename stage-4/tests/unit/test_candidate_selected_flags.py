"""`selected` on API candidates (R3.21): the top candidate of each title for executives, the top
candidate of the field for every other field. Builder-b, R3B.
"""

from datetime import datetime, timezone

from app.candidates import Candidate
from app.dossiers import field_json
from app.history import Selected

WHEN = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)


def _candidate(title, value, url):
    return Candidate(value=value, url=url, excerpt=value, provider="nimble", kind="own",
                     published_at=None, title=title)


def _view(field, ranked):
    return Selected(field=field, value="x", status="known", true_from=None, learned_at=WHEN,
                    citations=(), ranked=tuple((c, WHEN) for c in ranked))


def _selected_flags(body):
    return [c["selected"] for c in body["candidates"]]


def test_executives_selects_the_top_candidate_of_each_title():
    ranked = [
        _candidate("cfo", "Petra Garrow", "https://a.test/1"),
        _candidate("cfo", "Ana Silva", "https://a.test/2"),
        _candidate("coo", "Mirela Ellery", "https://a.test/3"),
        _candidate("cto", "Lucas Beaumont", "https://a.test/4"),
        _candidate("cto", "Ben Okafor", "https://a.test/5"),
    ]
    body = field_json(_view("executives", ranked), WHEN)
    assert _selected_flags(body) == [True, False, True, True, False]


def test_other_fields_select_only_the_first_candidate():
    ranked = [_candidate(None, "Dana Ruiz", "https://a.test/1"),
              _candidate(None, "Lee Park", "https://a.test/2")]
    body = field_json(_view("ceo", ranked), WHEN)
    assert _selected_flags(body) == [True, False]


def test_no_candidates_gives_no_flags():
    assert field_json(_view("executives", []), WHEN)["candidates"] == []
