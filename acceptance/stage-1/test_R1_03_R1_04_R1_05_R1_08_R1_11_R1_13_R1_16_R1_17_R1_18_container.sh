#!/usr/bin/env bash
# Usage: this-script /absolute/path/to/stage-1 /absolute/path/to/mock-web
set -euo pipefail
stage_dir=${1:?stage-1 directory required}
web_dir=${2:?mock-web directory required}
test_dir=$(cd "$(dirname "$0")" && pwd)
name="prover-stage1-$$"
tmp_dir=$(mktemp -d /tmp/prover-stage1.XXXXXX)
made_network=0
made_web=0
made_service=0
made_web_image=0
made_service_image=0
cleanup() {
  if (( made_service )); then timeout 20s docker rm -f "$name-service" >/dev/null || true; fi
  if (( made_web )); then timeout 20s docker rm -f "$name-web" >/dev/null || true; fi
  if (( made_network )); then timeout 20s docker network rm "$name-net" >/dev/null || true; fi
  if (( made_service_image )); then timeout 30s docker image rm "$name-service" >/dev/null || true; fi
  if (( made_web_image )); then timeout 30s docker image rm "$name-web" >/dev/null || true; fi
  python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1])' "$tmp_dir"
}
trap cleanup EXIT

test -f "$stage_dir/Dockerfile"
test -f "$stage_dir/RUN.md"
grep -Eq 'docker[[:space:]]+build' "$stage_dir/RUN.md"
grep -Eq 'docker[[:space:]]+run' "$stage_dir/RUN.md"
grep -Eiq 'webrouter(\[[^]]+\])?[[:space:]]*>=[[:space:]]*0\.12\.0' "$stage_dir/requirements.txt"
python3 "$test_dir/edge_corpus.py" "$web_dir/corpus/sample" "$tmp_dir/corpus"
timeout 600s flock /tmp/factory-heavy.lock docker build -t "$name-web" "$web_dir"
made_web_image=1
# The RUN.md build command uses stage-1 as context; the only substitutions are
# the image name and the isolated test network / port configuration.
timeout 600s flock /tmp/factory-heavy.lock docker build -t "$name-service" "$stage_dir"
made_service_image=1
timeout 20s docker network create --internal "$name-net" >/dev/null
made_network=1
timeout 20s docker run -d --name "$name-web" --network "$name-net" \
  -e MOCK_ADMIN_TOKEN=local-admin -v "$tmp_dir/corpus:/data/corpus:ro" \
  -v "$test_dir:/tests:ro" \
  -p 127.0.0.1:18201:8080 "$name-web" >/dev/null
made_web=1
deadline=$((SECONDS + 60))
timeout 20s docker run -d --name "$name-service" --network "$name-net" \
  --cpus 2 --memory 3g -e PORT=18200 -e NIMBLE_API_KEY=local \
  -e NIMBLE_BASE_URL="http://$name-web:8080/nimble" \
  -p 127.0.0.1:18200:18200 "$name-service" >/dev/null
made_service=1
until timeout 2s docker exec "$name-web" python3 -c 'import urllib.request,sys; urllib.request.urlopen(sys.argv[1],timeout=1)' "http://$name-service:18200/health" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then echo 'R1.13: service did not become healthy within 60 seconds' >&2; exit 1; fi
  sleep 0.2
done
timeout 10s docker exec "$name-web" python3 -c 'import json,urllib.request,sys; r=urllib.request.urlopen(sys.argv[1],timeout=5); assert r.status==200 and json.load(r)=={"status":"ok"}' "http://$name-service:18200/health"
timeout 900s docker exec -e DOSSIER_URL="http://$name-service:18200" \
  -e MOCK_URL=http://127.0.0.1:8080 -e MOCK_TOKEN=local-admin -e CORPUS_DIR=/data/corpus \
  "$name-web" python3 -m unittest discover -s /tests -v -p "${ACCEPTANCE_PATTERN:-test_*.py}"

# Verify the specified default when PORT is absent in a fresh instance.
timeout 20s docker rm -f "$name-service" >/dev/null
made_service=0
deadline=$((SECONDS + 60))
timeout 20s docker run -d --name "$name-service" --network "$name-net" \
  --cpus 2 --memory 3g -e NIMBLE_API_KEY=local \
  -e NIMBLE_BASE_URL="http://$name-web:8080/nimble" \
  -p 127.0.0.1:18202:8080 "$name-service" >/dev/null
made_service=1
until timeout 2s docker exec "$name-web" python3 -c 'import urllib.request,sys; urllib.request.urlopen(sys.argv[1],timeout=1)' "http://$name-service:8080/health" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then echo 'R1.18: default port did not become healthy' >&2; exit 1; fi
  sleep 0.2
done
