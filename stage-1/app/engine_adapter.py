"""Chooses the research engine: engine/ when present, the local stub otherwise."""

try:
    from engine import run_build  # noqa: F401 - builder-b's package, lands in P4
except ImportError:
    from ._stub_engine import run_build  # noqa: F401
