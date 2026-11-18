from types import SimpleNamespace

from app.research.evidence import Evidence

DOMAIN = "acme-robotics.test"


def claim(field, snippet, url="https://x.test/1"):
    return SimpleNamespace(field=f"$.{field}", snippet=snippet, url=url)


def test_R1_47_single_sentence_citation_supporting_the_claim_is_used():
    ev = Evidence(DOMAIN)
    ev.add_claims({"founded_year": 2014}, [claim("founded_year", "Acme Robotics was founded in 2014.")])
    assert [(c.field, c.value) for c in ev.finish()] == [("founded_year", 2014)]


def test_R1_47_R1_123_two_sentence_citation_does_not_support_the_claim():
    ev = Evidence(DOMAIN)
    ev.add_claims({"founded_year": 2014},
                  [claim("founded_year", "Acme Robotics was founded in 2014. Another sentence.")])
    assert ev.finish() == []


def test_R1_47_citation_for_a_different_value_is_not_the_claim():
    ev = Evidence(DOMAIN)
    ev.add_claims({"founded_year": 2015}, [claim("founded_year", "Acme Robotics was founded in 2014.")])
    assert ev.finish() == []
