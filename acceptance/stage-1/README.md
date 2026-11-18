# Stage 1 acceptance suite

Run against a dedicated service and mock instance. Tests reset both, change mock faults,
and replace service state; do not point them at shared or production data. The service
must be configured to use only the mock provider endpoints. Use a fresh instance with
CPU and memory limits from the specification.

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
