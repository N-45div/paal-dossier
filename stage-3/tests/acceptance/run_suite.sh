#!/bin/sh
# Build the stage-2 service image from the stage-2 folder and the mock web, start both on
# the Prover's port range (18200-18299), run the acceptance suite, then remove what this
# script started. Heavy work runs under the band-wide lock /tmp/factory-heavy.lock.
#
# Usage: stage-2/tests/acceptance/run_suite.sh [pytest args...]
#   MOCK_SRC   mock web build context (default: the read-only sample challenge folder)
#   CORPUS     corpus set mounted into the mock (default: its sample set)
#   SVC_PORT / MOCK_PORT  host ports (default 18210 / 18220)
set -eu

if [ -z "${PROVER_LOCKED:-}" ]; then
  PROVER_LOCKED=1 exec flock /tmp/factory-heavy.lock "$0" "$@"
fi

HERE=$(cd "$(dirname "$0")" && pwd)
STAGE=${STAGE_SRC:-$(cd "$HERE/../.." && pwd)}
MOCK_SRC=${MOCK_SRC:-/home/ndivij/buildathon/sf-buildathon-2026/challenges/dossier/web}
CORPUS=${CORPUS:-$MOCK_SRC/corpus/sample}
SVC_PORT=${SVC_PORT:-18210}
MOCK_PORT=${MOCK_PORT:-18220}
MOCK_ADMIN=${MOCK_ADMIN:-local-admin}
NET=prover-stage3-net
WEB=prover-stage3-web
SVC=prover-stage3-svc
export SVC_CONTAINER="$SVC"
WEB_IMG=prover-stage3-web
SVC_IMG=prover-stage3-svc
PY=${PYTHON:-python3}

# Merged corpus: the sample set (without its check file key.json and its traits) plus the
# Prover's own companies in prover-corpus/ (budget-heavy, trap-co) and their traits.
MERGED=$(mktemp -d /tmp/prover-corpus.XXXXXX)
for f in "$CORPUS"/*.json; do
  case "$(basename "$f")" in key.json|traits.json) ;; *) cp "$f" "$MERGED/" ;; esac
done
cp "$HERE"/prover-corpus/*.json "$MERGED/"

containers_down() {
  docker rm -f "$SVC" "$WEB" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
cleanup() {
  containers_down
  rm -rf "$MERGED"
}
trap cleanup EXIT INT TERM

# Ledger ids this script checks by running the image as the spec deploys it:
# R1.13 R1.19 R1.20 R1.21 R1.22 (Dockerfile built and run; only PORT and provider env set;
# no compose), R1.33 (webrouter install happens in the image build), R1.34-R1.41 (environment
# contract: PORT, NIMBLE_API_KEY, NIMBLE_BASE_URL, TAVILY_API_KEY, TAVILY_BASE_URL; keys are
# opaque non-empty strings), R1.44-R1.47 (CPU 2 and memory 3 GiB, via --cpus and --memory;
# health within 60 s), R1.56-R1.57 (health within 60 s of start).
containers_down
docker build -q -t "$WEB_IMG" "$MOCK_SRC" >/dev/null
docker build -q -t "$SVC_IMG" "$STAGE" >/dev/null
docker network create "$NET" >/dev/null

docker run -d --name "$WEB" --network "$NET" \
  -e MOCK_ADMIN_TOKEN="$MOCK_ADMIN" \
  -v "$MERGED:/data/corpus:ro" \
  -p "127.0.0.1:$MOCK_PORT:8080" "$WEB_IMG" >/dev/null

docker run -d --name "$SVC" --network "$NET" \
  --cpus 2 --memory 3g \
  -e PORT=8000 \
  -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL="http://$WEB:8080/nimble" \
  -e TAVILY_API_KEY=local -e TAVILY_BASE_URL="http://$WEB:8080/tavily" \
  -p "127.0.0.1:$SVC_PORT:8000" "$SVC_IMG" >/dev/null

deadline=$(( $(date +%s) + 60 ))
until curl -fsS "http://127.0.0.1:$SVC_PORT/health" >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "service did not become healthy within 60 s" >&2
    docker logs "$SVC" 2>&1 | tail -50 >&2 || true
    exit 1
  fi
  sleep 1
done

cd "$HERE"
BASE_URL="http://127.0.0.1:$SVC_PORT" \
MOCK_URL="http://127.0.0.1:$MOCK_PORT" \
MOCK_ADMIN="$MOCK_ADMIN" \
"$PY" -m pytest -p no:cacheprovider "$@"
