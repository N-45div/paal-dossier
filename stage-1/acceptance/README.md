# Stage 1 acceptance tests

Install pytest and requests in a host virtual environment, then run:

```sh
flock /tmp/factory-heavy.lock env DOSSIER_LOCK_HELD=1 python -m pytest -q stage-1/acceptance
```

Docker is required. `DOSSIER_STAGE`, `DOSSIER_MOCK`, and `DOSSIER_CORPUS` optionally select the stage build context, mock build context, and sample corpus. The defaults use this worktree and the local buildathon mock. The suite builds and removes uniquely named images, containers, and networks. `DOSSIER_RESOURCE_PREFIX` selects their prefix (default `prover`); `DOSSIER_PORT_MIN` and `DOSSIER_PORT_MAX` set an inclusive host-port range (default 18200–18299). The range must contain at least two valid ports. For example, a Gatekeeper run uses:

```sh
flock /tmp/factory-heavy.lock env DOSSIER_LOCK_HELD=1 DOSSIER_RESOURCE_PREFIX=gatekeeper DOSSIER_PORT_MIN=18300 DOSSIER_PORT_MAX=18399 python -m pytest -q stage-1/acceptance
```

The service and mock share an internal network, reached through a fixed-destination ingress relay. The suite applies 2 CPU / 3 GiB service limits. Set `DOSSIER_LOCK_HELD=1` only when the parent command already holds the shared lock; without it, the harness locks individual builds. No live provider key or public network is used by the service at runtime.

The explicitly skipped review-accounting cases identify requirements assigned to Gatekeeper review or classified by Lead as non-requirements. A skipped case is not a passing black-box verdict. The R1.106 mock-delay case may run for up to 300 seconds plus an 11-second check for late calls; Gatekeeper separately reviews live-provider timeouts.

`test_concurrency_model.py` starts seeded, overlapping HTTP requests and searches the possible serial histories subject to their real-time intervals. It checks the final observable users, sessions and dossier, plus concurrent export/replay; it uses no hooks in the service. Its randomized schedules are reproducible but do not exhaust every possible interleaving.
