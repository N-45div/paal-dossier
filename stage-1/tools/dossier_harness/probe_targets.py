"""What each sample company's key says must be found, and where contradicting values live."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from . import config
from .corpus_run import FIELDS, collapse, load_expected


@dataclass
class Target:
    """A supporting sentence for the expected value of one field."""
    field: str
    value: Any
    url: str
    excerpt: str  # whitespace-collapsed
    searchable: bool


@dataclass
class CompanyTargets:
    domain: str
    name: str
    expected: dict[str, Any] | None
    targets: list[Target] = field(default_factory=list)
    other_values: list[tuple[str, Any, str]] = field(default_factory=list)  # (field, value, url) labelled but not expected
    research_urls: dict[str, tuple[str, bool]] = field(default_factory=dict)  # field -> (url, page searchable)

    def required_fields(self) -> list[str]:
        return sorted({t.field for t in self.targets})


def _page_flags(corpus: dict[str, Any]) -> dict[str, bool]:
    """URL -> searchable in epoch 0 (a URL may have several entries)."""
    flags: dict[str, bool] = {}
    for page in corpus["pages"]:
        if 0 in page["epochs"]:
            flags[page["url"]] = page.get("searchable", True)
    return flags


def load_company(domain: str) -> CompanyTargets:
    corpus = json.loads((config.CORPUS_DIR / f"{domain}.json").read_text())
    key = json.loads((config.CORPUS_DIR / "key.json").read_text())[domain]
    expected = load_expected(config.CORPUS_DIR)[domain]
    flags = _page_flags(corpus)
    company = CompanyTargets(domain, corpus["names"][0], expected)
    for label in key.get("supports", []):
        if label["field"] not in FIELDS or expected is None:
            continue
        wanted = expected.get(label["field"])
        options = wanted if isinstance(wanted, list) else [wanted]
        if label["value"] in options and wanted is not None:
            company.targets.append(Target(label["field"], label["value"], label["url"], collapse(label["excerpt"]), flags.get(label["url"], True)))
        else:
            company.other_values.append((label["field"], label["value"], label["url"]))
    for entry in corpus.get("research", {}).get("nimble", {}).get("0", []):
        company.research_urls[entry["field"]] = (entry["url"], flags.get(entry["url"], True))
    return company


def load_all() -> list[CompanyTargets]:
    key = json.loads((config.CORPUS_DIR / "key.json").read_text())
    return [load_company(d) for d in sorted(key)]
