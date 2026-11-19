"""Recall report for the engine against the sample corpus (RL19 item 5). A QA tool, not deliverable.

Oracle per RL14, for one company and one epoch:
- every page with searchable != false served in that epoch, from ANY corpus company: a sentence
  counts when it names the target company and supports a value (engine.support);
- every nimble research claim for the company in that epoch whose excerpt is verbatim in the
  cited page and supports the claimed value.
A field is knowable when the oracle supports at least one value for it.

Usage (the mock web must be running and started with the corpus):
  recall.py <mock base url> <admin token> <corpus dir> <epoch> [--drop-query INDEX]
Prints one line per company and a summary. Units spent come from the engine's on_spend.
"""

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

REPO_STAGE = Path(__file__).resolve().parents[3] / "stage-1"
sys.path.insert(0, str(REPO_STAGE))

from engine import build as build_module  # noqa: E402
from engine import run_build  # noqa: E402
from engine.discovery import support_queries  # noqa: E402
from engine.support import FIELDS, is_verbatim_in_prose, normalize_ws, page_claims, supports  # noqa: E402


def set_epoch(base, token, epoch):
    request = urllib.request.Request(
        base + "/_mock/epoch",
        data=json.dumps({"epoch": epoch}).encode(),
        headers={"X-Mock-Admin": token, "Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(request, timeout=10).read()


def load_corpus(corpus_dir):
    companies = {}
    for path in sorted(Path(corpus_dir).glob("*.test.json")):
        companies[path.name[: -len(".json")]] = json.loads(path.read_text(encoding="utf-8"))
    return companies


def knowable(companies, domain, epoch):
    """field -> set of supported values, per RL14, for one company and one epoch."""
    support = {field: set() for field in FIELDS}
    page_texts = {}  # every page served in the epoch, searchable or not: research may cite any
    for doc in companies.values():
        for page in doc.get("pages", []):
            if epoch not in page.get("epochs", []):
                continue
            # The mock serves static_text when the entry has one, otherwise text (corpus.py).
            text = page.get("static_text", page.get("text", ""))
            page_texts.setdefault(page["url"], text)
            if page.get("searchable") is False:
                continue  # an unsearchable page is evidence only through a research claim
            for _sentence, field, value in page_claims(text, domain):
                support[field].add(value)
    research = companies.get(domain, {}).get("research", {}).get("nimble", {}).get(str(epoch), [])
    for claim in research:
        field, claimed = claim.get("field"), claim.get("value")
        text = page_texts.get(claim.get("url"))
        if field not in FIELDS or text is None or claimed is None:
            continue
        excerpt = normalize_ws(claim.get("excerpt", ""))
        if not is_verbatim_in_prose(excerpt, text):
            continue
        value = supports(excerpt, domain, field)
        if value is not None and str(value) == normalize_ws(str(claimed)).replace(",", ""):
            support[field].add(value)
    return support


def run_companies(base, token, corpus_dir, epoch, companies_wanted=None):
    companies = load_corpus(corpus_dir)
    set_epoch(base, token, epoch)
    rows = []
    for domain in sorted(companies):
        if companies_wanted and domain not in companies_wanted:
            continue
        oracle = knowable(companies, domain, epoch)
        spent = []
        started = time.time()
        result = run_build(domain, on_spend=spent.append)
        known = {f: result.fields[f]["value"] for f in FIELDS if result.fields[f]["value"] is not None}
        knowable_fields = {f for f in FIELDS if oracle[f]}
        missed = sorted(knowable_fields - set(known))
        wrong = sorted(f for f in known if known[f] not in oracle[f])
        rows.append(
            {
                "domain": domain,
                "knowable": len(knowable_fields),
                "known": len(set(known) & knowable_fields),
                "missed": missed,
                "wrong": wrong,
                "spent": result.spent,
                "seconds": round(time.time() - started, 2),
            }
        )
    return rows


def main(argv):
    base, token, corpus_dir, epoch = argv[1], argv[2], argv[3], int(argv[4])
    dropped_indexes = set()
    position = 0
    while "--drop-query" in argv[position:]:
        position = argv.index("--drop-query", position) + 1
        dropped_indexes.add(int(argv[position]))
    if dropped_indexes:
        original = build_module.support_queries

        def dropped(domain):
            return [q for i, q in enumerate(original(domain)) if i not in dropped_indexes]

        build_module.support_queries = dropped
    rows = run_companies(base, token, corpus_dir, epoch)
    total_k = total_known = 0
    for row in rows:
        total_k += row["knowable"]
        total_known += row["known"]
        print(json.dumps(row, ensure_ascii=False))
    print(f"SUMMARY epoch={epoch} knowable={total_k} known={total_known} "
          f"recall={total_known / total_k if total_k else 1:.3f} "
          f"max_spent={max(r['spent'] for r in rows)} "
          f"wrong={sum(len(r['wrong']) for r in rows)}")


if __name__ == "__main__":
    os.environ.setdefault("NIMBLE_API_KEY", "local")
    os.environ["NIMBLE_BASE_URL"] = sys.argv[1].rstrip("/") + "/nimble"
    main(sys.argv)
