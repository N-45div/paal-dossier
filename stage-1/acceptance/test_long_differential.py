"""Compare long-sentence HTTP results with independently enumerated supported fragments."""
import pytest

from long_examples import CASES, sentence, supporting_fragment_exists
from support import supports


@pytest.mark.parametrize("domain,field,value,prefix,expected", CASES, ids=[case[0] for case in CASES])
def test_long_sentence_differential(client, domain, field, value, prefix, expected):
    """R1.53 R1.104 R1.144-R1.162: Appendix A examples and each field, with long prose."""
    text = sentence(prefix)
    assert len(text) > 500 and len(prefix) < 500
    exists = supporting_fragment_exists(text, domain, field, value)
    assert exists is expected, "independent oracle disagrees with the example"
    c = client
    token = c.login()
    response = c.request("POST", "/dossiers", headers=c.auth(token, "long-differential"), json={"domain": domain})
    assert response.status_code == 202
    result = c.finish(domain, token)
    assert result["state"] == "ready"
    item = result["fields"][field]
    if not exists:
        assert item == {"value": None, "status": "unknown", "citations": []}
        return
    assert item["status"] == "known" and item["value"] == value and item["citations"]
    log = c.calls()
    assert sum(call["cost"] for call in log) <= 80
    for citation in item["citations"]:
        excerpt = " ".join(citation["excerpt"].split())
        assert 1 <= len(excerpt) <= 500 and supports(excerpt, domain, field, value)
        assert any(call["provider"] == citation["provider"] and any(served["url"] == citation["url"] and excerpt in " ".join(served["text"].split()) for served in call["served"]) for call in log)
