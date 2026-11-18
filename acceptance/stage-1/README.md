# Stage 1 acceptance suite

Run against a dedicated service and mock instance. Tests reset both, change mock faults,
and replace service state; do not point them at shared or production data. The service
must be configured to use only the mock provider endpoints. Use a fresh instance with
CPU and memory limits from the specification.

To build the Dockerfile and run the complete suite on an internal Docker network,
use the container-level checks (ports 18200 and 18201 must be available):

```sh
bash acceptance/stage-1/test_R1_03_R1_04_R1_05_R1_08_R1_11_R1_13_R1_16_R1_17_R1_18_container.sh \
  /absolute/path/to/stage-1 /absolute/path/to/challenges/dossier/web
```

The test client runs inside the mock container, so the isolated service network has
only the service and provider containers. Set `ACCEPTANCE_PATTERN=test_api.py` to
run the API subset while the research package is still a stub.

```sh
DOSSIER_URL=http://127.0.0.1:18200 MOCK_URL=http://127.0.0.1:18201 \
  MOCK_TOKEN=local-admin CORPUS_DIR=/path/to/web/corpus/sample \
  python3 -m unittest discover -s acceptance/stage-1 -v
```

Before starting the mock, create an augmented corpus and mount that directory at
`/data/corpus` in the mock container (the destination must not already exist):

```sh
python3 acceptance/stage-1/edge_corpus.py /path/to/web/corpus/sample /tmp/prover-stage1-corpus
```

Point `CORPUS_DIR` at this augmented directory. The original sample is preserved;
the extra cases exercise Appendix A boundaries and misleading header facts.

The suite uses only Python's standard library. `DOSSIER_URL`, `MOCK_URL`, and
`MOCK_TOKEN`, and `CORPUS_DIR` are required. To run a subset, use unittest's `-k` option. HTTP response
times are bounded by the client as well as asserted for burst requests. No live keys
or outbound network are used. A running build is polled for at most ten seconds.

Inspection-only: R1.00 (source provenance), R1.07 (provider calls use WebRouter),
R1.68 (password hashing implementation), R1.69 (out-of-scope features), and
R1.84 (live-provider timing; no live key is used). The provider log still checks
observable calls and costs. Appendix A cases cover many boundaries but do not
exhaust every phrase, suffix, alphabet or numerical spelling.
