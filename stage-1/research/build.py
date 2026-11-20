"""Entry point of a research build. Stub until the provider engine (WP3) lands."""

from .outcome import BuildOutcome, failed_outcome


def run_build(domain: str) -> BuildOutcome:
    """Research one company and return its outcome. Never raises."""
    return failed_outcome()
