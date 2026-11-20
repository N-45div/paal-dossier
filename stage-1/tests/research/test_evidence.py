"""Fields from evidence (stage-1.md section 4): one value per field, cited only by its own excerpts."""

from research.evidence import Evidence, decide_fields, evidence_from_pages
from research.fields import headcount_range_for

ACME = "acme-robotics.test"


def test_unknown_when_no_evidence():
    fields = decide_fields([])
    assert all(v == {"value": None, "citations": []} for v in fields.values())


def test_known_field_cites_its_excerpt_with_provider():
    pages = [("https://acme-robotics.test/about", "Acme Robotics was founded in 2014.")]
    fields = decide_fields(evidence_from_pages(ACME, pages))
    assert fields["founded_year"] == {
        "value": 2014,
        "citations": [
            {
                "url": "https://acme-robotics.test/about",
                "excerpt": "Acme Robotics was founded in 2014.",
                "provider": "nimble",
            }
        ],
    }


def test_header_facts_are_not_evidence():
    pages = [("https://a.test/x", 'Facts: {"founded_year": "2014"}\n\nAcme Robotics raised $12M.')]
    fields = decide_fields(evidence_from_pages(ACME, pages))
    assert fields["founded_year"]["value"] is None
    assert fields["funding_total"]["value"] == 12_000_000


def test_conflict_picks_value_with_most_distinct_excerpts_and_cites_only_it():
    evidence = [
        Evidence("ceo", "Dana Ruiz", "u1", "Dana Ruiz is the CEO of Acme Robotics."),
        Evidence("ceo", "Sam Ortiz", "u2", "Acme Robotics CEO: Sam Ortiz."),
        Evidence("ceo", "Dana Ruiz", "u3", "Dana Ruiz has led Acme Robotics as chief executive."),
    ]
    field = decide_fields(evidence)["ceo"]
    assert field["value"] == "Dana Ruiz"
    assert [c["excerpt"] for c in field["citations"]] == [
        "Dana Ruiz is the CEO of Acme Robotics.",
        "Dana Ruiz has led Acme Robotics as chief executive.",
    ]


def test_tie_goes_to_first_seen_value():
    evidence = [
        Evidence("hq_city", "Lisbon", "u1", "Acme Robotics is based in Lisbon."),
        Evidence("hq_city", "Porto", "u2", "Acme Robotics is based in Porto."),
    ]
    assert decide_fields(evidence)["hq_city"]["value"] == "Lisbon"


def test_duplicate_excerpt_is_cited_once():
    evidence = [
        Evidence("hq_city", "Lisbon", "u1", "Acme Robotics is based in Lisbon."),
        Evidence("hq_city", "Lisbon", "u1", "Acme Robotics is based in Lisbon."),
    ]
    assert len(decide_fields(evidence)["hq_city"]["citations"]) == 1


def test_headcount_band_for_counts():
    assert headcount_range_for(1) == "1-10"
    assert headcount_range_for(10) == "1-10"
    assert headcount_range_for(11) == "11-50"
    assert headcount_range_for(10000) == "5001-10000"
    assert headcount_range_for(10001) == "10001+"
    assert headcount_range_for(0) is None
