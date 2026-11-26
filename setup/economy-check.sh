#!/usr/bin/env bash
# Measure a frozen stage's research economy on the kickoff's sample mock web: provider units
# (from the mock's own priced call log) per correct field, for every sample company with a key.
#
#   bash economy-check.sh <result-repo> <stage-N> [revision]        revision defaults to main
#
# Builds the stage folder from the revision and the mock web from the kickoff checkout
# ($KICKOFF, default ~/buildathon/sf-buildathon-2026), runs them on a private Docker network
# and resets the mock before each company. Results go to band-work/economy/, never into the
# result repository. Needs no keys: every provider call goes to the mock.
set -euo pipefail
REPO="${1:?result repo}"; STAGE="${2:?stage folder, e.g. stage-4}"; REV="${3:-main}"
N="${STAGE#stage-}"; KICKOFF="${KICKOFF:-$HOME/buildathon/sf-buildathon-2026}"
OUT="${ECONOMY_OUT:-$HOME/buildathon/band-work/economy}/$STAGE-$(date -u +%Y%m%dT%H%M%SZ)"
HERE="$(cd "$(dirname "$0")" && pwd)"; W=$(mktemp -d); NET=economy-net; TOKEN=local-admin
mkdir -p "$OUT"
git -C "$REPO" archive "$REV" "$STAGE" | tar -x -C "$W"
cleanup() { docker logs economy-svc > "$OUT/service.log" 2>&1 || true
  docker rm -f economy-svc economy-web >/dev/null 2>&1 || true
  docker network rm $NET >/dev/null 2>&1 || true; rm -rf "$W"; }
trap cleanup EXIT
exec 9>/tmp/factory-heavy.lock; flock 9   # never overlaps a seat's heavy check
docker build -q -t economy-web "$KICKOFF/challenges/dossier/web" >/dev/null
docker build -q -t economy-svc "$W/$STAGE" >/dev/null
docker network create $NET >/dev/null 2>&1 || true
docker run -d --name economy-web --network $NET -e MOCK_ADMIN_TOKEN=$TOKEN \
  -v "$KICKOFF/challenges/dossier/web/corpus/sample:/data/corpus:ro" -p 18080:8080 economy-web >/dev/null
docker run -d --name economy-svc --network $NET -p 18901:8000 -e PORT=8000 \
  -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://economy-web:8080/nimble \
  -e TAVILY_API_KEY=local -e TAVILY_BASE_URL=http://economy-web:8080/tavily \
  -e KERNEL_API_KEY=local -e KERNEL_BASE_URL=http://economy-web:8080/kernel \
  -e BROWSERBASE_API_KEY=local -e BROWSERBASE_BASE_URL=http://economy-web:8080/browserbase \
  economy-svc >/dev/null
for _ in $(seq 1 120); do
  curl -sf localhost:18080/_mock/health >/dev/null && curl -sf localhost:18901/health >/dev/null && break; sleep 1
done
python3 "$HERE/economy_score.py" "$KICKOFF/challenges/dossier/web/corpus/sample/key.json" "$OUT" "$N" | tee "$OUT/summary.txt"
