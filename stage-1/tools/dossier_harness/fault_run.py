"""Provider faults must never surface as 5xx (R1.58, ruling L1.23)."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import config
from .api import MockAdmin, ServiceClient

DOMAIN = "windrush-bakery.test"
CASES = [
    ("nimble", "error", None), ("nimble", "rate_limit", None), ("nimble", "delay", 1), ("nimble", "delay", 5),
    ("tavily", "error", None), ("tavily", "rate_limit", None), ("tavily", "delay", 1), ("tavily", "delay", 5),
    ("both", "error", None), ("both", "rate_limit", None),
]


FAULTED_METHODS = ("search", "extract", "research")
FAULT_STATUS = {"error": 500, "rate_limit": 429}  # a delay fault answers 200, late


@dataclass
class FaultResult:
    case: str
    state: str
    seconds: float
    log_units: int
    spent_units: int
    problems: list[str] = field(default_factory=list)
    exercised: bool = True  # the faulted provider/method was really called during the build
    optional: bool = False  # the faulted provider is one the service need not use (tavily)
    informational: bool = False  # a delay case: reported, never a pass (M1.2 belongs to the independent suite)

    @property
    def passed(self) -> bool:
        return not self.problems and (self.informational or self.exercised or self.optional)

    @property
    def verdict(self) -> str:
        if self.problems:
            return "FAIL"
        if self.informational:
            return "informational (no 5xx, ready/failed; delay not attributed)"
        return "pass" if self.exercised else ("not exercised (optional provider unused)" if self.optional else "NOT EXERCISED (no faulted call reached the mock)")


def run_case(service: ServiceClient, mock: MockAdmin, provider: str, mode: str, seconds: float | None, timeout: float = 300) -> FaultResult:
    mock.reset()
    for target in (["nimble", "tavily"] if provider == "both" else [provider]):
        mock.fault(target, mode, seconds=seconds)
    service.reset({"now": config.FIXTURE_NOW, "users": config.USERS})
    ada = service.login("ada@example.com")
    started = time.monotonic()
    statuses = [service.create(ada, DOMAIN, "fault-run").status]
    with ThreadPoolExecutor(10) as pool:
        probes = [pool.submit(service.read, ada, DOMAIN) for _ in range(10)] + [pool.submit(service.listing, ada) for _ in range(5)]
        statuses += [p.result().status for p in probes]
    final = service.wait_built(ada, DOMAIN, timeout)
    statuses.append(final.status)
    calls = mock.log()
    label = f"{provider} {mode}{'' if seconds is None else f' {seconds}s'}"
    result = FaultResult(label, final.body["state"], time.monotonic() - started, sum(c["cost"] for c in calls), final.body["spent_units"])
    if any(s >= 500 or s == 0 for s in statuses):
        result.problems.append(f"bad statuses {sorted(set(statuses))}")
    if result.state not in ("ready", "failed"):
        result.problems.append(f"build ended {result.state}")
    if mode == "delay":
        # a call that times out costs its units though the mock may not log it (§9), so spent may exceed the log
        if result.spent_units < result.log_units:
            result.problems.append(f"spent_units {result.spent_units} < mock log {result.log_units}: calls were made but not counted")
    elif result.log_units != result.spent_units:
        result.problems.append(f"spent_units {result.spent_units} != mock log {result.log_units}")
    if result.log_units > 80:
        result.problems.append(f"{result.log_units} units over budget")
    targets = ["nimble", "tavily"] if provider == "both" else [provider]
    faulted = [c for c in calls if c["provider"] in targets and c["method"] in FAULTED_METHODS]
    if mode in FAULT_STATUS:
        faulted = [c for c in faulted if c["status"] == FAULT_STATUS[mode]]
    # error / rate_limit: exercised only when the log holds a call by the faulted provider and method answered with
    # that fault status. A delay cannot be attributed to a call from the log (ruling L1.33), so it is informational.
    result.exercised = bool(faulted)
    result.informational = mode == "delay"
    result.optional = provider == "tavily"
    # rate_limit is not permanent in the mock: a call refused three times is answered normally (README), so only `error` forces failure
    if provider == "both" and mode == "error":
        if result.state != "failed":
            result.problems.append("every call failed but the build did not end failed")
        if any(c["status"] == 200 for c in calls):
            result.problems.append("a call succeeded despite faults on both providers")
    return result
