# Stage 1 acceptance tests

Install pytest and requests in a host virtual environment, then run:

```sh
python -m pytest -q stage-1/acceptance
```

Docker is required. `DOSSIER_STAGE`, `DOSSIER_MOCK`, and `DOSSIER_CORPUS` optionally select the stage build context, mock build context, and sample corpus. The defaults use this worktree and the local buildathon mock. The suite builds and removes uniquely named `prover-` images, containers, and networks; only host ports 18200–18299 are used. The service and mock share an internal network, reached through a fixed-destination ingress relay. The suite applies the shared build lock and 2 CPU / 3 GiB service limits. No live provider key or public network is used by the service at runtime.

The explicitly skipped review-accounting cases identify requirements assigned to Gatekeeper review or classified by Lead as non-requirements. A skipped case is not a passing black-box verdict. The R1.106 mock-delay case may run for up to 300 seconds plus an 11-second check for late calls; Gatekeeper separately reviews live-provider timeouts.
