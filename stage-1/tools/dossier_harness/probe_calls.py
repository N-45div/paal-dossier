"""Issue candidate provider calls through WebRouter and record what each one surfaces (from /_mock/log)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from . import config
from .api import MockAdmin
from .corpus_run import FIELDS, collapse
from .probe_targets import CompanyTargets

DEPTHS = ("lite", "fast", "deep")
QUERY_TEMPLATES = ("domain", "name", "name headquarters", "name CEO", "name funding", "name founded", "name employees", "name legal name")
RESEARCH_SCHEMA = {"type": "object", "properties": {name: {"type": "string"} for name in FIELDS}}


@dataclass
class CallRecord:
    template: str  # e.g. "nimble:fast:name CEO", "nimble:research", "nimble:extract"
    cost: int
    error: str | None
    reached: set[str] = field(default_factory=set)  # fields whose expected value's supporting sentence was served
    urls: list[str] = field(default_factory=list)


def make_router():
    """A WebRouter pointed at the mock web."""
    from web_router import WebRouter  # imported late: needs the webrouter package

    web = f"http://127.0.0.1:{config.MOCK_PORT}"
    os.environ.update({"NIMBLE_API_KEY": "local", "NIMBLE_BASE_URL": f"{web}/nimble", "TAVILY_API_KEY": "local"})
    return WebRouter(provider="nimble", provider_config={"tavily": {"api_base_url": f"{web}/tavily"}})


def query_text(template: str, company: CompanyTargets) -> str:
    return company.domain if template == "domain" else template.replace("name", company.name, 1)


def reached_fields(company: CompanyTargets, new_calls: list[dict[str, Any]]) -> tuple[set[str], list[str]]:
    reached: set[str] = set()
    urls: list[str] = []
    for call in new_calls:
        for item in call.get("served") or []:
            text = collapse(item.get("text") or item.get("excerpt") or item.get("snippet") or "")
            url = item.get("url")
            urls.append(url)
            for target in company.targets:
                if target.excerpt in text and (url is None or url == target.url):
                    reached.add(target.field)
    return reached, urls


def record(mock: MockAdmin, company: CompanyTargets, template: str, action) -> CallRecord:
    before = len(mock.log())
    error = None
    try:
        action()
    except Exception as exc:  # a failed probe is data, not a crash
        error = type(exc).__name__
    fresh = mock.log()[before:]
    reached, urls = reached_fields(company, fresh)
    return CallRecord(template, sum(c["cost"] for c in fresh), error, reached, urls)


def probe_company(router, mock: MockAdmin, company: CompanyTargets) -> list[CallRecord]:
    mock.reset()
    records = []
    for provider in ("nimble", "tavily"):
        for depth in DEPTHS:
            for template in QUERY_TEMPLATES:
                query = query_text(template, company)
                records.append(record(mock, company, f"{provider}:{depth}:{template}",
                                      lambda: router.search(query, provider=provider, search_depth=depth, max_results=10)))
    research_query = f"{company.name} ({company.domain}): legal name, headquarters city, CEO, founding year, headcount, total funding"
    records.append(record(mock, company, "nimble:research", lambda: router.research(research_query, provider="nimble", output_schema=RESEARCH_SCHEMA, timeout=60)))
    missing = [t for t in company.targets if not any(t.field in r.reached for r in records)]
    for target in missing:  # can a direct extract of the supporting page reach it?
        records.append(record(mock, company, f"nimble:extract:{target.field}", lambda: router.extract([target.url], provider="nimble")))
    return records
