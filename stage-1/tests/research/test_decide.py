from app.research.decide import decide_fields
from app.research.evidence import Candidate


def cand(field, value, url, excerpt="x", provider="nimble"):
    return Candidate(field, value, url, excerpt, provider)


def test_R1_82_R1_38_unknown_when_no_candidates():
    fields = decide_fields([])
    assert set(fields) == {"legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total"}
    assert all(f == {"value": None, "status": "unknown", "citations": []} for f in fields.values())


def test_R1_48_citations_capped_at_five_distinct_urls():
    cands = [cand("ceo", "A B", f"https://u{i}.test", f"e{i}") for i in range(8)]
    cands.append(cand("ceo", "A B", "https://u0.test", "again"))
    citations = decide_fields(cands)["ceo"]["citations"]
    assert len(citations) == 5 and len({c["url"] for c in citations}) == 5


def test_R1_48_tie_is_deterministic():
    a = [cand("founded_year", 2015, "https://a.test"), cand("founded_year", 2014, "https://b.test")]
    assert decide_fields(a)["founded_year"]["value"] == decide_fields(list(reversed(a)))["founded_year"]["value"]
