#!/usr/bin/env bash
# Produce dossier-runway.com.json: the GET /dossiers/runway.com response of a stage's
# service, built against the live web.
#
#   NIMBLE_API_KEY=<key> tools/live-runway.sh <stage-folder>
#
# The key is passed to the container by name only (-e NIMBLE_API_KEY), so it never
# appears in argv, logs or files. NIMBLE_BASE_URL is left unset: live mode.
#
# Options (for a dry run against the mock web; not for the real run):
#   --nimble-base-url URL   set NIMBLE_BASE_URL in the container (e.g. http://mock:8080/nimble)
#   --network NAME          docker network to attach the container to
#   --out PATH              output file (default: <repo root>/dossier-runway.com.json)
#   --domain DOMAIN         company to research (default: runway.com)
set -euo pipefail

usage() { echo "usage: NIMBLE_API_KEY=<key> $0 <stage-folder> [--nimble-base-url URL] [--network NAME] [--out PATH] [--domain DOMAIN]" >&2; exit 2; }

root="$(cd "$(dirname "$0")/.." && pwd)"
stage="" base_url="" network="" out="$root/dossier-runway.com.json" domain="runway.com"
while [ $# -gt 0 ]; do
  case "$1" in
    --nimble-base-url) base_url="${2:?}"; shift 2 ;;
    --network) network="${2:?}"; shift 2 ;;
    --out) out="${2:?}"; shift 2 ;;
    --domain) domain="${2:?}"; shift 2 ;;
    -h|--help) usage ;;
    -*) usage ;;
    *) [ -z "$stage" ] || usage; stage="$1"; shift ;;
  esac
done
[ -n "$stage" ] || usage

if [ -z "${NIMBLE_API_KEY:-}" ]; then
  echo "NIMBLE_API_KEY is not set: refusing to start. Export your Nimble key in the environment and run again." >&2
  exit 1
fi
[ -f "$stage/Dockerfile" ] || { echo "no Dockerfile in $stage" >&2; exit 2; }
for tool in docker curl python3; do
  command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 2; }
done

port="${PORT:-18150}"
name="live-runway-$$"
image="live-runway-img-$$"
base="http://127.0.0.1:$port"
tmp="$(mktemp -d)"

cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker rmi "$image" >/dev/null 2>&1 || true
  rm -rf "$tmp"
}
trap cleanup EXIT

echo "building $stage ..."
timeout 900 docker build -q -t "$image" "$stage" >/dev/null

run_args=(-d --name "$name" -p "127.0.0.1:$port:$port" -e "PORT=$port" -e NIMBLE_API_KEY)
[ -z "$base_url" ] || run_args+=(-e "NIMBLE_BASE_URL=$base_url")
[ -z "$network" ] || run_args+=(--network "$network")
timeout 60 docker run "${run_args[@]}" "$image" >/dev/null

echo "waiting for the service ..."
for _ in $(seq 1 60); do
  curl -fsS -m 2 "$base/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS -m 2 "$base/health" >/dev/null || { echo "service did not become healthy" >&2; exit 1; }

now="$(python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).isoformat())')"
curl -fsS -m 10 -X POST -H 'Content-Type: application/json' \
  -d "{\"now\": \"$now\", \"users\": []}" "$base/_test/reset" >/dev/null

email="live-$$@example.com"
token="$(curl -fsS -m 10 -X POST -H 'Content-Type: application/json' \
  -d "{\"email\": \"$email\", \"password\": \"correct horse battery\", \"display_name\": \"Live\"}" \
  "$base/auth/signup" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')"
auth="Authorization: Bearer $token"

curl -fsS -m 10 -X POST -H "$auth" -H 'Content-Type: application/json' \
  -H "Idempotency-Key: live-runway-$$" -d "{\"domain\": \"$domain\"}" "$base/dossiers" >/dev/null

echo "researching $domain (up to 300 s) ..."
state=""
for _ in $(seq 1 100); do
  curl -fsS -m 5 -H "$auth" -o "$tmp/dossier.json" "$base/dossiers/$domain"
  state="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["state"])' "$tmp/dossier.json")"
  [ "$state" = building ] || break
  sleep 3
done

if [ "$state" != ready ]; then
  echo "build ended in state '$state', not 'ready': nothing written" >&2
  exit 3
fi
cp "$tmp/dossier.json" "$out"
echo "wrote $out"
