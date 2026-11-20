"""Unit units: the budget cap, refusal refunds and charged non-answers (stage-1.md section 9)."""

import pytest

from research.budget import UNIT_CAP, Budget
from research.calls import REFUSED, SKIPPED, UNANSWERED, Refused, Unanswered, perform


def no_sleep(_seconds):
    return None


def test_cap_is_eighty_units():
    assert UNIT_CAP == 80
    budget = Budget()
    assert all(budget.reserve(10) for _ in range(8))
    assert budget.reserve(1) is False
    assert budget.spent == 80


def test_answered_call_is_charged():
    budget = Budget()
    outcome = perform(budget, 5, lambda: "page")
    assert outcome.answered and outcome.value == "page"
    assert budget.spent == 5


def test_refused_call_costs_nothing_and_is_retried(monkeypatch):
    monkeypatch.setattr("research.calls.time.sleep", no_sleep)
    budget = Budget()
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise Refused("500")
        return "ok"

    outcome = perform(budget, 4, flaky)
    assert outcome.answered and outcome.value == "ok"
    assert budget.spent == 4  # only the answered attempt is charged


def test_refusal_after_all_attempts_is_refused_and_free(monkeypatch):
    monkeypatch.setattr("research.calls.time.sleep", no_sleep)
    budget = Budget()

    def refused():
        raise Refused("500")

    assert perform(budget, 25, refused, attempts=4) == REFUSED
    assert budget.spent == 0


def test_unanswered_call_is_charged_and_not_retried():
    budget = Budget()
    calls = []

    def timed_out():
        calls.append(1)
        raise Unanswered("timeout")

    assert perform(budget, 3, timed_out) == UNANSWERED
    assert len(calls) == 1
    assert budget.spent == 3


def test_unexpected_exception_is_charged_not_raised():
    budget = Budget()

    def broken():
        raise ValueError("boom")

    assert perform(budget, 2, broken).status == "unanswered"
    assert budget.spent == 2


def test_call_beyond_cap_is_skipped():
    budget = Budget()
    assert budget.reserve(79)
    calls = []
    outcome = perform(budget, 2, lambda: calls.append(1))
    assert outcome == SKIPPED
    assert calls == []
    assert budget.spent == 79


def test_refusal_retry_respects_cap(monkeypatch):
    monkeypatch.setattr("research.calls.time.sleep", no_sleep)
    budget = Budget()
    assert budget.reserve(80)  # cap reached by others
    assert perform(budget, 1, lambda: "x").status == "skipped"


@pytest.mark.parametrize("units", [0, 1, 80])
def test_reserve_at_boundaries(units):
    budget = Budget()
    assert budget.reserve(units) is True
    assert budget.spent == units
