"""Ledger coverage for the stage-1 acceptance suite.

Usage: python3 coverage.py [path/to/LEDGER.md]

An id counts as named when a suite file (test_*.py, conftest.py, run_suite.sh) mentions it,
either alone (R1.94) or inside a range it states (R1.220-R1.231 names every id in that range).

Ids that no request can exercise are listed in STRUCTURAL with the reason and the place that
checks them instead. They are reported, never silently dropped.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[1] / "LEDGER.md"

SUITE_GLOBS = ["test_*.py", "conftest.py", "oracle.py", "run_suite.sh"]
RANGE = re.compile(r"R1\.(\d+)(?:\s*-\s*R1\.(\d+))?")

STRUCTURAL = {
    # process or packaging rules: checked by the gatekeeper review or the image build
    "R1.1": "introduction; no testable behaviour",
    "R1.2": "process: build from the supplied requirements (gatekeeper review)",
    "R1.3": "process: no existing products' code used (gatekeeper review, provenance)",
    "R1.4": "permission statement; no behaviour",
    "R1.14": "freedom of language and storage; no behaviour",
    "R1.15": "compose optional; no behaviour",
    "R1.16": "submission form; checked by the image build (run_suite.sh)",
    "R1.17": "freedom of language; no behaviour",
    "R1.18": "freedom of language; no behaviour",
    "R1.29": "routing rule: every provider call goes through web_router (gatekeeper code review; the mock log shows the calls reached the provider endpoints)",
    "R1.30": "dependency manifest lists webrouter>=0.12.0 (gatekeeper check of stage-1/requirements.txt)",
    "R1.31": "provider API calls by any other route are not permitted (gatekeeper code review)",
    "R1.32": "install of webrouter in the Docker build (run_suite.sh builds the image)",
    "R1.52": "runtime assets in the image (gatekeeper check of the built image)",
    "R1.53": "runtime assets in the image; no external services at runtime (gatekeeper check)",
    "R1.50": "outbound network limit at run time is not enforced by this suite (needs a network policy; gatekeeper check)",
    "R1.51": "ephemeral disk; no testable behaviour",
    "R1.146": "out of scope: email verification and password reset are not required",
    "R1.12": "out of scope: contact data, people search, other fields (fields test checks the six keys only)",
    "R1.253": "state need not survive an abrupt restart; a restart test is not in this suite yet",
    "R1.27": "live judging with a working Nimble key only; not exercised by the mock suite",
    "R1.28": "routing rule: the service reaches providers only through WebRouter (gatekeeper code review)",
    "R1.42": "Tavily base URL passed to WebRouter in provider_config (gatekeeper code review of the call)",
    "R1.43": "the provider_config snippet itself (gatekeeper code review of the call)",
    "R1.192": "live-provider timing rule (no deadline for slow providers, 300 s bound); the mock is not a live provider",
    "R1.240": "exports are private artifacts: handling rule, checked by the gatekeeper review",
}


def ledger_ids(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"^### (R1\.\d+)\b", text, flags=re.M)


def named_ids() -> set[str]:
    found: set[str] = set()
    for pattern in SUITE_GLOBS:
        for f in HERE.glob(pattern):
            text = f.read_text(encoding="utf-8")
            for m in RANGE.finditer(text):
                lo = int(m.group(1))
                hi = int(m.group(2)) if m.group(2) else lo
                if hi < lo:
                    continue
                found |= {f"R1.{n}" for n in range(lo, hi + 1)}
    return found


if __name__ == "__main__":
    all_ids = ledger_ids(LEDGER) if LEDGER.exists() else []
    if not all_ids:
        print(f"ledger not found at {LEDGER}; named ids: {len(named_ids())}")
        sys.exit(0)
    named = named_ids()
    structural = [i for i in all_ids if i in STRUCTURAL and i not in named]
    uncovered = [i for i in all_ids if i not in named and i not in STRUCTURAL]
    covered = [i for i in all_ids if i in named]
    print(f"ledger ids: {len(all_ids)}  named by suite: {len(covered)}  "
          f"structural (reasoned): {len(structural)}  uncovered: {len(uncovered)}")
    if uncovered:
        print("uncovered: " + ", ".join(uncovered))
    for i in structural:
        print(f"  {i}: {STRUCTURAL[i]}")
