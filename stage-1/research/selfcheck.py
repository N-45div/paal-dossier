"""Self-check against a corpus key: one build per company, then spend, fields and label agreement.

    NIMBLE_API_KEY=<any> NIMBLE_BASE_URL=http://<mock>/nimble PYTHONPATH=stage-1 \\
        python -m research.selfcheck <corpus>/key.json

Prints one JSON line per company. A field counts as agreeing when it is known and its value is one
the key labels for it, or when it is unknown and the key labels nothing for it. Labels are a subset of
what the rules support, so a known field the key does not label is reported, not counted as wrong.
"""

import json
import sys

from .engine import run_build
from .fields import FIELDS


def main(argv: list[str]) -> int:
    with open(argv[1], encoding="utf-8") as handle:
        key = json.load(handle)
    failures = 0
    for domain in sorted(key):
        labels: dict[str, set] = {}
        for label in key[domain].get("supports", []):
            if label["field"] in FIELDS:
                labels.setdefault(label["field"], set()).add(label["value"])
        outcome = run_build(domain)
        agreeing = []
        for name in FIELDS:
            value = outcome.fields[name]["value"]
            if (value is None and name not in labels) or (value is not None and value in labels.get(name, ())):
                agreeing.append(name)
        failures += len(FIELDS) - len(agreeing)
        print(
            json.dumps(
                {
                    "domain": domain,
                    "ok": outcome.ok,
                    "spent_units": outcome.spent_units,
                    "fields": {name: outcome.fields[name]["value"] for name in FIELDS},
                    "agreeing_fields": len(agreeing),
                }
            )
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
