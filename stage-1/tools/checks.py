#!/usr/bin/env python3
"""Limits, load and fault checks against the built image: startup time, 50-in-flight load, provider faults.

    python3 stage-1/tools/checks.py [--no-build] [startup] [load] [faults]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dossier_harness import fault_run, load_run, stack, startup_run  # noqa: E402


def check_startup() -> bool:
    times = startup_run.measure()
    print("startup (cold, warm, warm):", ", ".join(f"{t:.1f}s" for t in times), f"(limit {startup_run.LIMIT_SECONDS:.0f}s)")
    return max(times) < startup_run.LIMIT_SECONDS


def check_load(service, mock) -> bool:
    report = load_run.run_load(service, mock)
    print(f"load: {len(report.replies)} replies, max latency {report.max_latency:.2f}s, problems: {report.problems or 'none'}")
    return not report.problems


def check_faults(service, mock) -> bool:
    ok = True
    for provider, mode, seconds in fault_run.CASES:
        r = fault_run.run_case(service, mock, provider, mode, seconds)
        print(f"fault {r.case:18} state={r.state:7} wall={r.seconds:5.1f}s units={r.log_units:3d}/{r.spent_units:3d} {r.verdict} {r.problems or ''}")
        ok = ok and r.passed
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("which", nargs="*", choices=["startup", "load", "faults"], default=["startup", "load", "faults"])
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    ok = True
    with stack.running(build=not args.no_build) as (service, mock):
        stack.stop_service()
        if "startup" in args.which:
            ok = check_startup() and ok
        stack.start_service()
        if "load" in args.which:
            ok = check_load(service, mock) and ok
        if "faults" in args.which:
            ok = check_faults(service, mock) and ok
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
