"""Docker-backed integration checks (slow). Run: pytest stage-1/tests/integration --integration"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from dossier_harness import corpus_run, fault_run, load_run, stack, startup_run  # noqa: E402

pytestmark = pytest.mark.skipif("--integration" not in sys.argv, reason="needs docker; pass --integration")


@pytest.fixture(scope="module")
def running():
    with stack.running() as clients:
        yield clients


def test_startup_time_under_limits(running):
    assert max(startup_run.measure(2)) < startup_run.LIMIT_SECONDS
    stack.start_service()


def test_load_with_50_in_flight(running):
    report = load_run.run_load(*running)
    assert not report.problems


@pytest.mark.parametrize("case", fault_run.CASES, ids=lambda c: "-".join(map(str, c)))
def test_provider_faults_never_5xx(running, case):
    assert not fault_run.run_case(*running, *case).problems


def test_corpus_matches_key(running):
    expected = corpus_run.load_expected()
    results = [corpus_run.run_company(*running, d, e) for d, e in sorted(expected.items())]
    assert not [p for r in results for p in r.problems]
