"""Traps and budget pressure, on the Prover's own corpus companies (prover-corpus/).

- budget-heavy.test: 41 searchable pages that mention the company, plus a page with facts.
  Demand is pushed toward the 80-unit cap; spend and the call log must stay within it and
  the build must still end ready.
- trap-co.test: a page where funding is only stated as negated ("reportedly in talks to
  raise"), and a research claim whose excerpt is not a sentence of any served page. Nothing
  in the evidence supports any of its six fields, so every field must be unknown.

These companies exist only in the merged corpus that run_suite.sh mounts. Ledger ids named
per test: R1.10, R1.11, R1.100, R1.111, R1.190, R1.206, R1.232, R1.236, R1.257, R1.268,
R1.286, R1.110.
"""
import time

from conftest import (await_settled, call, check_dossier_fields, mock_calls, new_key,
                      start_build, total_cost)

BUDGET = "budget-heavy.test"
TRAP = "trap-co.test"


def test_budget_pressure_never_exceeds_80_units(env):
    # R1.11, R1.236, R1.206, R1.100
    r = start_build(env["ada"], BUDGET)
    assert r.status_code == 202, r.text
    d = await_settled(env["ada"], BUDGET, timeout=120)
    calls = mock_calls()
    assert d["state"] == "ready", d["state"]
    assert d["spent_units"] <= 80, d["spent_units"]
    assert total_cost(calls) <= 80, total_cost(calls)
    assert d["spent_units"] == total_cost(calls)
    check_dossier_fields(d, BUDGET, calls)


def test_trap_company_has_no_supported_fields(env):
    # R1.10, R1.110, R1.111, R1.257, R1.268, R1.286
    r = start_build(env["ada"], TRAP)
    assert r.status_code == 202, r.text
    d = await_settled(env["ada"], TRAP, timeout=120)
    calls = mock_calls()
    # the research claims are not sentences of any served page, so they cannot be cited
    assert d["state"] in ("ready", "failed")
    assert all(f["value"] is None for f in d["fields"].values()), {
        name: f["value"] for name, f in d["fields"].items() if f["value"] is not None}
    for f in d["fields"].values():
        assert f["citations"] == []
    check_dossier_fields(d, TRAP, calls)
