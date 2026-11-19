"""Company research: Appendix A support rules, page parsing and the build engine."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.research.evidence import build_fields
from app.research.plan import gather
from app.research.providers import ProviderCalls, Timeouts
from app.research.support import FIELDS


def _unknown_fields() -> dict[str, dict]:
    return {field: {"value": None, "status": "unknown", "citations": []} for field in FIELDS}


async def run_build(domain: str, spend: Callable[[int], None], *, router: Any = None) -> dict:
    """Research ``domain`` and decide its six fields (L1.01).

    ``spend(units)`` is called once per charged provider call. ``ok`` is false exactly when no provider call succeeded.
    """
    calls = ProviderCalls(spend, Timeouts.for_environment(), router=router)
    try:
        gathered = await gather(calls, domain)
    finally:
        await calls.close()
    if gathered.successes == 0:
        return {"ok": False, "fields": _unknown_fields()}
    return {"ok": True, "fields": build_fields(gathered, domain)}
