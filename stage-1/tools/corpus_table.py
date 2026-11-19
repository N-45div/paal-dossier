#!/usr/bin/env python3
"""One command: build images, start mock + service, build every sample company, print the M1.1/M1.5 table.

    python3 stage-1/tools/corpus_table.py [--no-build] [--no-tavily] [company.test ...]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dossier_harness import config, corpus_run, stack  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("companies", nargs="*", help="domains to build (default: every sample company)")
    parser.add_argument("--no-build", action="store_true", help="reuse already built images")
    parser.add_argument("--no-tavily", action="store_true", help="start the service with Nimble only")
    args = parser.parse_args()
    expected = corpus_run.load_expected()
    domains = args.companies or sorted(expected)
    with stack.running(tavily=not args.no_tavily, build=not args.no_build) as (service, mock):
        results = [corpus_run.run_company(service, mock, d, expected.get(d)) for d in domains]
    print(corpus_run.format_table(results))
    return 1 if any(r.problems for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
