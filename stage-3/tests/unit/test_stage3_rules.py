"""Stage 3 pure rules (R3B): executives titles and page true_from (Effective / Published)."""

from datetime import date

from app.pages import page_meta
from app.support import supported_executives

DOMAIN = "acme-robotics.test"


def test_cfo_phrase_with_a_person_is_a_cfo_candidate():
    text = "Ana Silva is the chief financial officer of Acme Robotics."
    assert supported_executives(DOMAIN, text) == {"cfo": "Ana Silva"}


def test_cto_abbreviation_with_colon_form():
    assert supported_executives(DOMAIN, "Acme Robotics CTO: Ben Okafor.") == {"cto": "Ben Okafor"}


def test_ceo_sentence_is_not_an_executive():
    assert supported_executives(DOMAIN, "Acme Robotics CEO: Sam Ortiz.") == {}


def test_negated_title_is_not_supported():
    assert supported_executives(DOMAIN, "Acme Robotics is not seeking a COO, Ben Okafor said.") == {}


def test_effective_header_is_the_true_from_date():
    meta = page_meta({"Effective": "2025-09-01", "Published": "2026-01-10T00:00:00Z"},
                     "https://acme-robotics.test/team", DOMAIN)
    assert meta.true_from == date(2025, 9, 1)


def test_missing_effective_takes_utc_date_of_published():
    meta = page_meta({"Published": "2026-01-10T23:30:00-05:00"},
                     "https://acme-robotics.test/team", DOMAIN)
    assert meta.true_from == date(2026, 1, 11)


def test_invalid_effective_falls_back_then_none_without_published():
    assert page_meta({"Effective": "2025-02-30"}, "https://acme-robotics.test/t", DOMAIN).true_from is None
    assert page_meta({}, "https://acme-robotics.test/t", DOMAIN).true_from is None
