"""Ledger items whose verdict is assigned to review or are non-requirements."""
import pytest


@pytest.mark.parametrize("ledger_id,method", [
    pytest.param("R1.6", "Gatekeeper executes the exact RUN.md build/start commands", id="R1.6-manual-commands"),
    pytest.param("R1.10", "Gatekeeper reviews provider access through WebRouter", id="R1.10-static-review"),
    pytest.param("R1.11", "Gatekeeper reviews manifest and Docker install", id="R1.11-static-review"),
    pytest.param("R1.12", "Gatekeeper reviews provider configuration", id="R1.12-static-review"),
    pytest.param("R1.19", "not applicable (negative statement)", id="R1.19-not-applicable"),
    pytest.param("R1.88", "not applicable (negative statement)", id="R1.88-not-applicable"),
])
def test_review_or_not_applicable(ledger_id, method):
    pytest.skip(f"{ledger_id}: {method}; no black-box verification claimed")
