"""Stage 4 history typing of investors (stage-4 spec, Investors; ledger R4.40), black-box over HTTP
against the real mock, with a two-epoch fixture.

Fixture: larkspur-health.test. Its filing page "companies-register.test/entity/28330914/allotments"
exists only in epoch 1 and names Thornbury Ventures as an investor (a filing, so a member at once).
At epoch 0 the investors value is null (no member); at epoch 1 it is ["Thornbury Ventures"].

The rule for the type of a history entry (R4.40): a name in the new value and not in the earlier
one counts as a correction when its true_from and the earlier value's true_from are both not null
and its true_from is on or before the earlier value's. The entry is `correction` when every name in
exactly one of the two values counts as a correction, and `change` otherwise. The earlier value is
null here, so its true_from is null and the name does not count: the entry is `change`.
"""
import time

import requests

from conftest import MOCK_URL, await_settled, call, login, mock_reset, mock_weather, new_key, reset_service, start_build

import pytest

DOMAIN = "larkspur-health.test"
NEW_INVESTOR = "Thornbury Ventures"


def _mock_epoch(epoch):
    r = requests.post(MOCK_URL + "/_mock/epoch", headers={"X-Mock-Admin": "local-admin"},
                      json={"epoch": epoch}, timeout=10)
    assert r.status_code == 204, r.text


@pytest.fixture(scope="module")
def two_epochs():
    r = requests.get(MOCK_URL + "/_mock/health", timeout=5)
    assert r.status_code == 200, "mock web not reachable at MOCK_URL"
    mock_reset(0)
    mock_weather(False)
    reset_service()
    token = login("ada@example.com")
    r = start_build(token, DOMAIN, key=new_key())
    assert r.status_code == 202, r.text
    at_epoch0 = await_settled(token, DOMAIN, timeout=120)
    _mock_epoch(1)
    r = call("POST", f"/dossiers/{DOMAIN}/refresh", token=token, key=new_key(), body={}, timeout=10)
    assert r.status_code in (200, 202), r.text
    at_epoch1 = await_settled(token, DOMAIN, timeout=120)
    hist = call("GET", f"/dossiers/{DOMAIN}/history", token=token, timeout=10)
    assert hist.status_code == 200, hist.text
    return {"token": token, "epoch0": at_epoch0, "epoch1": at_epoch1, "history": hist.json()}


def _investor_entries(history):
    """The investors entries of the history body, whatever its container shape."""
    if isinstance(history, dict) and isinstance(history.get("fields"), dict):
        return list(history["fields"].get("investors", []))
    if isinstance(history, dict) and isinstance(history.get("investors"), list):
        return list(history["investors"])
    raise AssertionError(f"history body has no investors list: {str(history)[:600]}")


def _member_true_from(field, name):
    froms = [c.get("true_from") for c in field["candidates"] if c["value"] == name and c.get("true_from")]
    return min(froms) if froms else None


def _rule_type(earlier, later):
    """R4.40 typing, derived from the two field states (names and their true_from by R4.38)."""
    earlier_names = set(earlier["value"] or [])
    later_names = set(later["value"] or [])
    earlier_from = earlier.get("true_from")
    def counts(name):
        name_from = _member_true_from(later, name)
        return (name_from is not None and earlier_from is not None and name_from <= earlier_from)
    exactly_one = earlier_names ^ later_names
    all_correct = all(counts(n) for n in exactly_one if n in later_names) and not (exactly_one & earlier_names)
    return "correction" if exactly_one and all_correct else "change"


# R4.40: a history entry for investors is typed by name (names counted as corrections by true_from,
# and the entry is `correction` only when every name in exactly one of the two values counts)
def test_investors_history_entry_type_follows_the_name_rule(two_epochs):
    earlier = two_epochs["epoch0"]["fields"]["investors"]
    later = two_epochs["epoch1"]["fields"]["investors"]
    assert later["value"] and later["value"] != earlier["value"], (earlier["value"], later["value"])
    assert NEW_INVESTOR in later["value"], later["value"]
    expected = _rule_type(earlier, later)
    entries = _investor_entries(two_epochs["history"])
    assert entries, two_epochs["history"]
    assert entries[-1].get("type") == expected, (expected, entries[-1])
