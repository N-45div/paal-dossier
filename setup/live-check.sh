#!/usr/bin/env bash
# Build a frozen stage folder and research real companies on the live web through Nimble.
#
#   bash live-check.sh <result-repo> <stage-N> [domain ...]      default domain: runway.com
#
# Follows the participant guide's steps for dossier-runway.com.json, on a separate copy of
# the stage folder taken from the integration branch, with the key read from ~/.nimble.env.
# Results go to band-work/live/, never into the result repository, so a run in progress
# never sees them; commit dossier-runway.com.json yourself after the last stage is final.
# Spends real Nimble credit. Waits for the band's shared lock so it never overlaps a check.
set -euo pipefail
REPO="${1:?result repo}"; STAGE="${2:?stage folder, e.g. stage-1}"; shift 2
DOMAINS=("${@:-runway.com}")
OUT="${LIVE_OUT:-$HOME/buildathon/band-work/live}"; PORT="${LIVE_PORT:-18900}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ); WORK=$(mktemp -d)
NAME=$(echo "live-$STAGE-$STAMP" | tr '[:upper:]' '[:lower:]')   # image names must be lowercase
mkdir -p "$OUT"
[ -f "$HOME/.nimble.env" ] || { echo "missing ~/.nimble.env" >&2; exit 1; }
set -a; . "$HOME/.nimble.env"; set +a
git -C "$REPO" archive main "$STAGE" | tar -x -C "$WORK"
cleanup() {   # keep the service log: it shows whether a field was not found or the build gave up waiting
  docker logs "$NAME" > "$OUT/$STAGE-$STAMP.service.log" 2>&1 || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT

exec 9>/tmp/factory-heavy.lock; flock 9
docker build -q -t "$NAME" "$WORK/$STAGE" >/dev/null
docker run -d --name "$NAME" -p "$PORT:8000" -e PORT=8000 \
  -e NIMBLE_API_KEY -e NIMBLE_BASE_URL=https://sdk.nimbleway.com \
  -e TAVILY_API_KEY=unavailable -e TAVILY_BASE_URL=https://api.tavily.com \
  -e KERNEL_API_KEY=unavailable -e KERNEL_BASE_URL=https://api.onkernel.com \
  -e BROWSERBASE_API_KEY=unavailable -e BROWSERBASE_BASE_URL=https://api.browserbase.com \
  "$NAME" >/dev/null
flock -u 9
BASE="http://localhost:$PORT"
for _ in $(seq 1 120); do curl -sf "$BASE/health" >/dev/null && break; sleep 1; done
curl -sf "$BASE/health" >/dev/null || { echo "service never became healthy"; docker logs "$NAME" | tail -20; exit 1; }
TOKEN=$(curl -s -X POST "$BASE/auth/signup" -H 'Content-Type: application/json' \
  -d '{"email": "live@example.com", "password": "live-dossier", "display_name": "Live"}' \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["token"])')

for D in "${DOMAINS[@]}"; do
  start=$(date +%s)
  curl -s -X POST "$BASE/dossiers" -H "Authorization: Bearer $TOKEN" \
    -H "Idempotency-Key: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
    -H 'Content-Type: application/json' -d "{\"domain\": \"$D\"}" >/dev/null
  for _ in $(seq 1 180); do
    curl -s "$BASE/dossiers/$D" -H "Authorization: Bearer $TOKEN" | grep -q '"state": *"building"' || break
    sleep 5
  done
  F="$OUT/$STAGE-$D-$STAMP.json"
  curl -s "$BASE/dossiers/$D" -H "Authorization: Bearer $TOKEN" > "$F"
  echo "== $D ($(( $(date +%s) - start ))s) -> $F"
  python3 - "$F" <<'P'
import json, sys
d = json.load(open(sys.argv[1])); print("state:", d.get("state"))
for f, v in (d.get("fields") or {}).items():
    print(f"  {f:<16} {str(v.get('value'))[:70]}")
P
done
