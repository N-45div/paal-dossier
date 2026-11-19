"""A scripted stand-in for dossier.engine.run_build, so server tests need no providers."""

import threading
from types import SimpleNamespace

from dossier.server.model import FIELD_NAMES


def citation(url, excerpt, provider="nimble"):
    return {"url": url, "excerpt": excerpt, "provider": provider}


def result(ok=True, spent=0, values=None):
    """A BuildResult-like object. `values` maps field name -> (value, citations)."""
    values = values or {}
    fields = {}
    for name in FIELD_NAMES:
        value, citations = values.get(name, (None, []))
        fields[name] = SimpleNamespace(value=value, citations=list(citations))
    return SimpleNamespace(ok=ok, spent_units=spent, fields=fields)


class FakeEngine:
    """Returns `outcome` for every build; `gate` holds a build until it is set."""

    def __init__(self, outcome=None):
        self.outcome = outcome or result(ok=True, spent=5)
        self.calls: list[str] = []
        self.gate = threading.Event()
        self.gate.set()
        self.lock = threading.Lock()

    def __call__(self, domain, cancel):
        with self.lock:
            self.calls.append(domain)
        self.gate.wait(timeout=5)
        return self.outcome
