"""The API candidate carries `title` only for an executives candidate (R3.18). Builder-b, R3B."""

from datetime import datetime, timezone

from app.candidates import Candidate
from app.dossiers import candidate_json

WHEN = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)


def _candidate(**changes) -> Candidate:
    base = dict(value="Ana Silva", url="https://acme-robotics.test/team",
                excerpt="Ana Silva is the chief financial officer of Acme Robotics.",
                provider="nimble", kind="own", published_at=None)
    base.update(changes)
    return Candidate(**base)


def test_executives_candidate_carries_its_title_beside_value():
    body = candidate_json(_candidate(title="cfo"), WHEN, True, WHEN)
    assert body["title"] == "cfo"
    assert body["value"] == "Ana Silva"


def test_other_field_candidate_has_no_title_key():
    body = candidate_json(_candidate(), WHEN, False, WHEN)
    assert "title" not in body
