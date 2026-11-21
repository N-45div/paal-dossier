"""Stage 4 provider failure (stage-4 spec, Provider failure; ledger R4.57-R4.61, pkg R4P), against the
real mock. Faults are persistent: mode `error` answers 500 on every listed call until cleared.

The time bound is R1.191 (stage-1 section 8, kept in the stage-4 ledger): a build whose provider
calls each answer within one second ends within 10 seconds of the request that started it. The mock
answers fast, so the all-fail build must end failed within 10 seconds.
Expected values are derived from the clock, the corpus and the spec text, not from the service.
"""
import time

from conftest import SAMPLE_DOMAINS, await_settled, call, mock_faults, new_key, start_build, reset_service

BOUND_SECONDS = 10.0  # R1.191: calls answering within one second; the build ends within 10 seconds
PROVIDERS = ("nimble", "tavily")
METHODS = ("search", "extract", "research")


def _set_all(mode):
    for provider in PROVIDERS:
        for method in METHODS:
            mock_faults(provider, [method], mode)


def _clear_all():
    _set_all("none")


def test_every_call_failing_ends_failed_within_the_bound_with_no_spend(env):
    # R4.60 (all calls to every provider fail: failed within the time bound), R4.61 (refused calls cost
    # nothing), R1.191 (10 seconds for calls that answer within one second)
    domain = SAMPLE_DOMAINS[0]
    _set_all("error")
    try:
        started = time.monotonic()
        r = start_build(env["ada"], domain, key=new_key())
        assert r.status_code == 202, r.text
        d = await_settled(env["ada"], domain, timeout=BOUND_SECONDS + 30)
        elapsed = time.monotonic() - started
    finally:
        _clear_all()
    assert d["state"] == "failed", d
    assert d["spent_units"] == 0, d["spent_units"]
    print(f"R1.191 all-fail build elapsed {elapsed:.2f}s (bound {BOUND_SECONDS}s)")
    assert elapsed <= BOUND_SECONDS, f"all-fail build took {elapsed:.2f}s, bound is {BOUND_SECONDS}s"
    for name, fld in d["fields"].items():
        assert fld["value"] is None, (name, fld)
