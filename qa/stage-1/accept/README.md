# Stage 1 independent HTTP acceptance suite

Run from the prover checkout, with Docker available and Python 3 plus `pytest` and `httpx` installed:

```sh
flock /tmp/factory-heavy.lock python3 -m pytest qa/stage-1/accept --service-root /home/ndivij/buildathon/band-work/paal-dossier
```

Change `--service-root` to the worktree whose `stage-1/Dockerfile` is being tested. The suite builds that image and the supplied mock web, starts both on a private internal network, and connects host loopback ports 18200–18299 through a small relay on a separate bridge. The service has no outbound network access. The suite removes its own containers, images and networks afterward. No live provider credentials are used. A single run holds the factory lock for all Docker work. Failures include the request and response via pytest assertions. Export snapshots can contain credentials; do not publish captured exports or verbose test output containing tokens.

The body-size boundary and concurrent-request tests connect directly to the service's internal Docker address, avoiding relay upload interruptions and timing overhead. Docker must be local and its internal bridge reachable from the host.

The mock and oracle default to the sample corpus. To run against a different mock corpus directory, add `--corpus /absolute/path/to/corpus`; both the provider mount and the oracle use that directory. Company cases and the evidence set are generated from its JSON files at epoch 0, not from sample-specific expected facts.

The controlled-corpus cases start a separate deployment with synthetic company pages. Run just those cases with `-q qa/stage-1/accept/test_synthetic.py --service-root /home/ndivij/buildathon/band-work/paal-dossier`, under the same factory lock.
