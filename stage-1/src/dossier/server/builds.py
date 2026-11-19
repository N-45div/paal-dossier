"""Build lifecycle: start a build on a worker, then apply its outcome (spec 8, RL1.7, RL1.8).

`start_build` runs with the store lock held. The worker calls the injected runner; the
outcome is applied only if the build is still current (same generation, same dossier build).
"""

from dataclasses import dataclass

from dossier.server.model import FIELD_NAMES, Build, Dossier, FieldValue, known_field
from dossier.server.service import Service
from dossier.server.store import Store


@dataclass(frozen=True)
class Outcome:
    ok: bool
    spent: int
    fields: dict[str, FieldValue] | None


def start_build(service: Service, dossier: Dossier) -> None:
    """Caller holds the store lock."""
    store = service.store
    build = Build(dossier.domain, store.clock.now(), store.generation)
    dossier.build = build
    store.running.add(build)
    service.executor.submit(_run, service, build)


def _run(service: Service, build: Build) -> None:
    try:
        outcome = _outcome(service.runner(build.domain, build.cancel))
    except Exception:  # the engine must not raise (RL1.3); a fault is a failed build
        outcome = Outcome(False, 0, None)
    _finish(service.store, build, outcome)


def _outcome(result: object) -> Outcome:
    spent = getattr(result, "spent_units", 0)
    spent = spent if type(spent) is int and spent >= 0 else 0
    if not getattr(result, "ok", False):
        return Outcome(False, spent, None)
    raw_fields = getattr(result, "fields", {}) or {}
    fields = {}
    for name in FIELD_NAMES:
        raw = raw_fields.get(name)
        checked = known_field(name, getattr(raw, "value", None), getattr(raw, "citations", None))
        fields[name] = checked or FieldValue()
    return Outcome(True, spent, fields)


def _finish(store: Store, build: Build, outcome: Outcome) -> None:
    with store.lock:
        store.running.discard(build)
        if build.generation != store.generation:
            return  # a reset or import happened meanwhile: this result is stale
        dossier = store.dossiers.get(build.domain)
        if dossier is None or dossier.build is not build:
            return
        dossier.build = None
        dossier.spent_units += outcome.spent
        if outcome.ok:
            dossier.state = "ready"
            dossier.fields = outcome.fields
            dossier.researched_at = build.requested_at
        else:
            dossier.state = "failed"
        store.lock.notify_all()
