"""50-in-flight mixed load (R1.12, R1.15, R1.76, R1.88, R1.120a, R1.58)."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import config
from .api import MockAdmin, Reply, ServiceClient, call

IN_FLIGHT = 50
LATENCY_LIMIT = 5.0
SHARED_DOMAIN = "ashgrove-solar.test"
OTHER_DOMAINS = ["corvid-security.test", "halvorsen-robotics.test", "mosaic-freight.test", "pemberton-analytics.test", "windrush-bakery.test"]


@dataclass
class LoadReport:
    replies: list[Reply] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def max_latency(self) -> float:
        return max(r.seconds for r in self.replies)


def _expect(report: LoadReport, condition: bool, message: str) -> None:
    if not condition:
        report.problems.append(message)


def _successful_domain_searches(calls: list[dict], domain: str) -> int:
    return sum(1 for c in calls if c["method"] == "search" and c["query"] == domain and c["status"] == 200)


def run_load(service: ServiceClient, mock: MockAdmin, build_timeout: float = 120) -> LoadReport:
    mock.reset()
    service.reset({"now": config.FIXTURE_NOW, "users": config.USERS})
    report = LoadReport()
    ada = service.login("ada@example.com")
    bob = service.login("bob@example.com")
    pool = ThreadPoolExecutor(IN_FLIGHT)
    base = service.base

    # Wave 1: many keys for one domain, one key repeated, other domains, signups, logins, reads.
    shared_keys = [pool.submit(service.create, ada if i % 2 else bob, f" WWW.{SHARED_DOMAIN.upper()}. " if i % 3 == 0 else SHARED_DOMAIN, f"shared-{i}") for i in range(20)]
    same_key = [pool.submit(service.create, ada, OTHER_DOMAINS[0], "one-key") for _ in range(20)]
    others = [pool.submit(service.create, ada, d, f"other-{d}") for d in OTHER_DOMAINS[1:]]
    signups = [pool.submit(call, "POST", f"{base}/auth/signup", {"email": f"load{i}@example.com", "password": "12345678", "display_name": f"L{i}"}) for i in range(15)]
    logins = [pool.submit(service.login, "ada@example.com") for _ in range(10)]
    reads = [pool.submit(service.listing, ada) for _ in range(10)] + [pool.submit(service.read, ada, SHARED_DOMAIN) for _ in range(10)]

    shared = [f.result() for f in shared_keys]
    same = [f.result() for f in same_key]
    signed_up = [f.result() for f in signups]
    report.replies += shared + same + signed_up + [f.result() for f in others + reads]
    for f in logins:
        f.result()

    _expect(report, sorted(r.status for r in shared).count(202) == 1 and all(r.status in (200, 202) for r in shared), "shared domain: not exactly one 202 over different keys")
    _expect(report, len({r.body["dossier_id"] for r in shared}) == 1, "shared domain: more than one dossier id")
    _expect(report, [r.status for r in same].count(202) == 1 and [r.status for r in same].count(200) == 19, "same key: not exactly one 202 and 19 replays")
    _expect(report, len({str(r.body) for r in same}) == 1, "same key: replay bodies differ")
    _expect(report, all(r.status == 201 for r in signed_up), "signup: not all 201")
    _expect(report, len({r.body["user_id"] for r in signed_up}) == len(signed_up), "signup: user ids repeat")

    for domain in [SHARED_DOMAIN, *OTHER_DOMAINS]:
        built = service.wait_built(ada, domain, build_timeout)
        _expect(report, built.status == 200 and built.body["state"] == "ready", f"{domain}: build did not end ready")

    time.sleep(0.5)
    first_builds = mock.log()
    for domain in [SHARED_DOMAIN, *OTHER_DOMAINS]:
        _expect(report, _successful_domain_searches(first_builds, domain) == 1, f"{domain}: first wave did not run exactly one build")

    # Wave 2: concurrent refreshes of one domain run one build; another key refreshes while idle.
    refreshes = [pool.submit(service.refresh, ada, SHARED_DOMAIN, f"refresh-{i}") for i in range(20)]
    refreshed = [f.result() for f in refreshes]
    report.replies += refreshed
    _expect(report, all(r.status == 202 for r in refreshed), "refresh: not all 202")
    _expect(report, len({r.body["dossier_id"] for r in refreshed}) == 1, "refresh: ids differ")
    service.wait_built(ada, SHARED_DOMAIN, build_timeout)
    time.sleep(0.5)

    calls = mock.log()
    listing = service.listing(ada, "?limit=200")
    report.replies.append(listing)
    _expect(report, len(listing.body["dossiers"]) == 1 + len(OTHER_DOMAINS), "listing: wrong dossier count")
    _expect(report, _successful_domain_searches(calls, SHARED_DOMAIN) >= 2, "refresh started no new build")
    for domain in OTHER_DOMAINS:
        _expect(report, _successful_domain_searches(calls, domain) == 1, f"{domain}: built more than once without a refresh")
    total_spent = sum(d["spent_units"] for d in listing.body["dossiers"])
    _expect(report, total_spent == sum(c["cost"] for c in calls), f"spent_units total {total_spent} != mock log {sum(c['cost'] for c in calls)}")
    _expect(report, all(r.status < 500 and r.status != 0 for r in report.replies), "a request returned 5xx or failed")
    _expect(report, report.max_latency < LATENCY_LIMIT, f"max latency {report.max_latency:.2f}s")
    pool.shutdown()
    return report
