# Stage 1 acceptance tests

Install pytest and requests in a host virtual environment, then run:

```sh
python -m pytest -q stage-1/acceptance
```

Docker is required. `DOSSIER_STAGE`, `DOSSIER_MOCK`, and `DOSSIER_CORPUS` optionally select the stage build context, mock build context, and sample corpus. The defaults use this worktree and the local buildathon mock. The suite builds and removes uniquely named `prover-` images, containers, and an internal network; only host ports 18200–18299 are used. It applies the shared build lock and 2 CPU / 3 GiB service limits. No live provider key or public network is used at runtime.
