"""Compare long-sentence HTTP results with independently enumerated supported fragments."""
import pytest
import time
import requests

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


def test_forty_kilobyte_sentence_build_finishes(client):
    """R1.105 R1.76: fast providers and a long sentence must not hold the build or requests."""
    c = client
    token = c.login()
    domain = "timing-proof.test"
    # Calibrate the mock itself before the build; clear those calibration calls
    # so the subsequent cost/log assertions cover the service's calls only.
    checks = [
        ("/nimble/v2/search", {"query": domain}),
        ("/nimble/v2/extract", {"url": "https://timing-proof.test/about"}),
        ("/nimble/v2/agents/runs", {"input": domain, "output_schema": {"type": "object", "properties": {"founded_year": {"type": "integer"}}}}),
    ]
    for path, body in checks:
        begin = time.monotonic()
        calibrated = requests.post(c.mock + path, json=body, timeout=1)
        assert calibrated.status_code == 200 and time.monotonic() - begin < 1
    c.control("reset", {"epoch": 0})
    started = time.monotonic()
    response = c.request("POST", "/dossiers", headers=c.auth(token, "timing"), json={"domain": domain})
    assert response.status_code == 202
    try:
        result = c.finish(domain, token, seconds=max(.001, 10 - (time.monotonic() - started)))
    except AssertionError:
        log = [(call["method"], call["status"], call["cost"]) for call in c.calls()]
        pytest.fail(f"Build still running at 10 seconds; mock calls (method, status, cost): {log}", pytrace=False)
    assert time.monotonic() - started <= 10 and result["state"] == "ready"
    calls = c.calls()
    assert any(len(served["text"]) >= 40000 for call in calls for served in call["served"] if served["url"] == "https://timing-proof.test/about")
    assert sum(call["cost"] for call in calls) <= 80
    founder = result["fields"]["founded_year"]
    assert founder["status"] == "known" and founder["value"] == 2014 and founder["citations"]
    for citation in founder["citations"]:
        excerpt = " ".join(citation["excerpt"].split())
        assert supports(excerpt, domain, "founded_year", 2014)
        assert any(call["provider"] == citation["provider"] and any(served["url"] == citation["url"] and excerpt in " ".join(served["text"].split()) for served in call["served"]) for call in calls)
