# Stage 1 independent HTTP acceptance suite

Run from the prover checkout with local Docker, Python 3 and `venv` available. The runner builds a small wheelhouse image, installs pytest and httpx into a temporary venv with `--no-index`, and holds `/tmp/factory-heavy.lock` throughout:

```sh
python3 qa/stage-1/accept/run.py --service-root /home/ndivij/buildathon/band-work/paal-dossier --name-prefix prover --port-start 18200 --port-end 18299
```

For the gatekeeper seat, use its own prefix and assigned ports:

```sh
python3 qa/stage-1/accept/run.py --service-root /home/ndivij/buildathon/band-work/paal-dossier --name-prefix gatekeeper --port-start 18300 --port-end 18399
```

Change `--service-root` to the worktree whose `stage-1/Dockerfile` is being tested. The suite builds that image and the supplied mock web, starts both on a private internal network, and connects the assigned host loopback ports through a small relay on a separate bridge. The service has no outbound network access. The suite removes its own containers, images and networks afterward. No live provider credentials are used. Failures include the request and response via pytest assertions. Export snapshots can contain credentials; do not publish captured exports or verbose test output containing tokens.

The body-size boundary and concurrent-request tests connect directly to the service's internal Docker address, avoiding relay upload interruptions and timing overhead. Docker must be local and its internal bridge reachable from the host.

The mock and oracle default to the sample corpus. To run against a different mock corpus directory, add `--corpus /absolute/path/to/corpus`. The oracle uses corpus metadata to enumerate pages and research claims, then obtains full text through the running mock's extract endpoint and served-text log. It resets the log before each measured build (RL25).

The controlled-corpus cases start separate deployments with synthetic company pages. One uses a transparent HTTP proxy to measure simultaneous provider extracts during a delayed build (RL13). To select them, add `--test-path qa/stage-1/accept/test_synthetic.py -q` to the runner command. Additional unrecognized options are passed to pytest; for example, `-s -q -k evidence_and_cost` prints per-company measurements. Ledger IDs and verbatim requirement text are indexed in [CLAIMS.md](CLAIMS.md).

The HTTP/1.0 upload with neither Content-Length nor Transfer-Encoding is included as an RL28 interpretation probe; its expected result is awaiting Lead's clarification. Treat its failure as inconclusive until then.
