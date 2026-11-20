"""The build engine: `research.run_build(domain)` from the research package (WP3).

`run_build` never raises. It returns an object with `ok`, `fields` and `spent_units`.
Until the research package is installed the import below falls back to a build that
always fails, so the service still starts and answers every other endpoint.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

try:
    from research import run_build
except ImportError as error:  # only before the research package is present
    print(f"research package unavailable, builds will fail: {error}", file=sys.stderr)

    def run_build(domain: str) -> Any:
        return SimpleNamespace(ok=False, fields={}, spent_units=0)
