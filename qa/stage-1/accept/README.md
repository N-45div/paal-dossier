# Stage 1 independent HTTP acceptance suite

Run from the prover checkout, with Docker available and Python 3 plus `pytest` and `httpx` installed:

```sh
flock /tmp/factory-heavy.lock python3 -m pytest qa/stage-1/accept --service-root /home/ndivij/buildathon/band-work/paal-dossier
```

Change `--service-root` to the worktree whose `stage-1/Dockerfile` is being tested. The suite builds that image and the supplied mock web, starts both on a private internal network, and connects host loopback ports 18200–18299 through a small relay on a separate bridge. The service has no outbound network access. The suite removes its own containers, images and networks afterward. No live provider credentials are used. A single run holds the factory lock for all Docker work. Failures include the request and response via pytest assertions. Export snapshots can contain credentials; do not publish captured exports or verbose test output containing tokens.
