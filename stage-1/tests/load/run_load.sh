#!/bin/sh
# Build the image, start mock web + service (2 CPUs, 3 GiB) and run the load test.
# usage: tests/load/run_load.sh [seconds] [fake]   ("fake" mounts the load stand-in for app.research)
set -eu
here=$(cd "$(dirname "$0")" && pwd)
stage=$(cd "$here/../.." && pwd)
corpus=${CORPUS_DIR:?set CORPUS_DIR to the sample corpus folder}
prefix=${PREFIX:-builder-a}
port=${PORT_HOST:-18010}
cleanup() { timeout 30 docker rm -f "$prefix-load-svc" "$prefix-load-web" >/dev/null 2>&1 || true
            timeout 30 docker network rm "$prefix-load-net" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup
flock /tmp/factory-heavy.lock timeout 550 docker build -q -t "$prefix-dossier" "$stage" >/dev/null
docker network create "$prefix-load-net" >/dev/null
docker run -d --name "$prefix-load-web" --network "$prefix-load-net" -e MOCK_ADMIN_TOKEN=local \
  -v "$corpus:/data/corpus:ro" "${WEB_IMAGE:-$prefix-web}" >/dev/null
mount=""
[ "${2:-}" = fake ] && mount="-v $here/fake_research:/srv/app/research:ro"
docker run -d --name "$prefix-load-svc" --network "$prefix-load-net" --cpus 2 --memory 3g \
  -p "$port:8080" -e PORT=8080 -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL="http://$prefix-load-web:8080/nimble" \
  -e TAVILY_API_KEY=local -e TAVILY_BASE_URL="http://$prefix-load-web:8080/tavily" $mount "$prefix-dossier" >/dev/null
for i in $(seq 60); do curl -sf "localhost:$port/health" >/dev/null && break; sleep 1; done
"${PYTHON:-python3}" -I "$here/load_test.py" "http://localhost:$port" "${1:-20}"
