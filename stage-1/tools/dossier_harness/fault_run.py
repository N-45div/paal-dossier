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


@dataclass
class FaultResult:
    case: str
    state: str
    seconds: float
    log_units: int
    spent_units: int
    problems: list[str] = field(default_factory=list)


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
    if result.log_units != result.spent_units:
        result.problems.append(f"spent_units {result.spent_units} != mock log {result.log_units}")
    if result.log_units > 80:
        result.problems.append(f"{result.log_units} units over budget")
    if provider == "both" and result.state != "failed":
        result.problems.append("every call failed but the build did not end failed")
    if provider == "both" and any(c["status"] == 200 for c in calls):
        result.problems.append("a call succeeded despite faults on both providers")
    return result
