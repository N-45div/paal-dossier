"""Build every sample company and compare with the key (measures M1.1 and M1.5)."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from . import config
from .api import MockAdmin, ServiceClient

FIELDS = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")
BUDGET = 80


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_expected(corpus_dir=config.CORPUS_DIR) -> dict[str, dict[str, Any] | None]:
    """Oracle per company: expected['1']['0'] when the key has one (ruling L1.24), else None."""
    key = json.loads((corpus_dir / "key.json").read_text())
    return {domain: (entry.get("expected") or {}).get("1", {}).get("0") for domain, entry in key.items()}


def field_matches(expected: Any, field_state: dict[str, Any]) -> bool:
    if expected is None:
        return field_state["status"] == "unknown"
    options = expected if isinstance(expected, list) else [expected]
    return field_state["status"] == "known" and field_state["value"] in options


def cited_excerpts_served(fields: dict[str, Any], calls: list[dict[str, Any]]) -> list[str]:
    """Citations whose excerpt is not a whitespace-collapsed part of a text the mock served for that URL."""
    served: dict[str, list[str]] = {}
    for call in calls:
        for item in call.get("served") or []:
            if isinstance(item, dict) and "url" in item:
                served.setdefault(item["url"], []).append(collapse(item.get("text") or item.get("excerpt") or ""))
    missing = []
    for name, field_state in fields.items():
        for citation in field_state["citations"]:
            if not any(collapse(citation["excerpt"]) in text for text in served.get(citation["url"], [])):
                missing.append(f"{name}: {citation['url']}")
    return missing


@dataclass
class CompanyResult:
    domain: str
    state: str
    seconds: float
    log_units: int
    spent_units: int
    domain_searches: int
    fields: dict[str, Any]
    mismatches: list[str] = field(default_factory=list)
    unserved: list[str] = field(default_factory=list)
    has_oracle: bool = False

    @property
    def problems(self) -> list[str]:
        found = list(self.mismatches) + [f"unserved citation {u}" for u in self.unserved]
        if self.state != "ready":
            found.append(f"state {self.state}")
        if self.log_units > BUDGET:
            found.append(f"{self.log_units} units over budget")
        if self.log_units != self.spent_units:
            found.append(f"spent_units {self.spent_units} != mock log {self.log_units}")
        if self.domain_searches != 1:
            found.append(f"{self.domain_searches} successful bare-domain searches")
        return found


def run_company(service: ServiceClient, mock: MockAdmin, domain: str, expected: dict[str, Any] | None, timeout: float = 120) -> CompanyResult:
    mock.reset()
    service.reset({"now": config.FIXTURE_NOW, "users": config.USERS})
    headers = service.login("ada@example.com")
    started = time.monotonic()
    service.create(headers, domain, "corpus-run")
    reply = service.wait_built(headers, domain, timeout)
    seconds = time.monotonic() - started
    body = reply.body
    calls = mock.log()
    result = CompanyResult(
        domain=domain,
        state=body["state"],
        seconds=seconds,
        log_units=sum(c["cost"] for c in calls),
        spent_units=body["spent_units"],
        domain_searches=sum(1 for c in calls if c["method"] == "search" and c["query"] == domain and c["status"] == 200),
        fields=body["fields"],
        has_oracle=expected is not None,
        unserved=cited_excerpts_served(body["fields"], calls),
    )
    if expected is not None:
        for name in FIELDS:
            if not field_matches(expected.get(name), body["fields"][name]):
                result.mismatches.append(f"{name}: got {body['fields'][name]['value']!r}, expected {expected.get(name)!r}")
    return result


def format_table(results: list[CompanyResult]) -> str:
    lines = [f"{'company':28} {'state':7} {'wall_s':>6} {'units':>5} {'spent':>5} {'dsrch':>5}  " + " ".join(f"{n[:6]:>6}" for n in FIELDS)]
    for r in results:
        marks = []
        for name in FIELDS:
            known = r.fields[name]["status"] == "known"
            bad = any(m.startswith(name + ":") for m in r.mismatches)
            marks.append(("FAIL" if bad else ("ok" if r.has_oracle else ("val" if known else "unk"))))
        lines.append(f"{r.domain:28} {r.state:7} {r.seconds:6.1f} {r.log_units:5d} {r.spent_units:5d} {r.domain_searches:5d}  " + " ".join(f"{m:>6}" for m in marks))
    units = [r.log_units for r in results]
    oracle = [r for r in results if r.has_oracle]
    good = sum(len(FIELDS) - len(r.mismatches) for r in oracle)
    lines.append(f"units per build: max {max(units)}, mean {sum(units) / len(units):.1f} (budget {BUDGET})")
    lines.append(f"oracle fields correct: {good}/{len(FIELDS) * len(oracle)} over {len(oracle)} companies with an expected value")
    for r in results:
        for problem in r.problems:
            lines.append(f"  PROBLEM {r.domain}: {problem}")
    return "\n".join(lines)
