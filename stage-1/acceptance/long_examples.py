"""Independent long-sentence corpus adapted from Appendix A examples."""
import json
from pathlib import Path
import re

from support import supports

# domain, field, candidate value, sentence prefix, whether a fragment should support it
CASES = [
    ("diff-ceo-a.test", "ceo", "Dana Ruiz", "Dana Ruiz has led Diff Ceo A as chief executive since 2021", True),
    ("diff-ceo-b.test", "ceo", "Sam Ortiz", "Diff Ceo B CEO: Sam Ortiz", True),
    ("diff-year.test", "founded_year", 2014, "Diff Year was founded in 2014", True),
    ("diff-people.test", "headcount_range", "51-200", "Diff People employs about 120 people", True),
    ("diff-rumour.test", "funding_total", 40000000, "Diff Rumour is reportedly in talks to raise $40M", False),
    ("diff-office.test", "hq_city", "Porto", "Diff Office opened a sales office in Porto", False),
    ("diff-legal.test", "legal_name", "Diff Legal, Inc.", "Diff Legal has registered name Diff Legal, Inc.", True),
    ("diff-headquarters.test", "hq_city", "Lisbon", "Diff Headquarters is headquartered in Lisbon", True),
    ("diff-funding.test", "funding_total", 12000000, "Diff Funding has raised $12M", True),
]


def sentence(prefix):
    return prefix + " neutral" * 70 + "."


def supporting_fragment_exists(text, domain, field, value):
    """Brute-force word-boundary windows using only the independent Appendix A oracle."""
    if not supports(text, domain, field, value):
        return False
    words = list(re.finditer(r"\S+", text))
    for start in words:
        for end in words:
            if end.end() <= start.start():
                continue
            if end.end() - start.start() > 500:
                break
            if supports(text[start.start():end.end()], domain, field, value):
                return True
    return False


def write_fixtures(directory):
    """Add only self-contained provider data; sample corpus remains read-only."""
    for domain, _, _, prefix, _ in CASES:
        name = domain.split(".")[0].replace("-", " ").title()
        page = {"url": f"https://{domain}/about", "kind": "own", "epochs": [0, 1],
                "searchable": True, "published_at": None, "true_from": None,
                "title": name + " company", "text": sentence(prefix), "facts": {},
                "lineage": {"canonical": None, "first_published_by": None, "registrant": domain}}
        entry = {"domain": domain, "names": [name], "pages": [page],
                 "research": {"nimble": {"0": [], "1": []}}}
        (Path(directory) / (domain + ".json")).write_text(json.dumps(entry))
