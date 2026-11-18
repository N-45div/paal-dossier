import pytest

from app import builds


async def instant_build(domain, spend):
    """Default research stand-in: finishes at once with nothing found."""
    return {"ok": True, "fields": {}}


@pytest.fixture(autouse=True)
def fake_research(monkeypatch):
    monkeypatch.setattr(builds, "run_build", instant_build)
