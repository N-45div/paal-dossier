#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} != --locked ]]; then
  exec flock /tmp/factory-heavy.lock "$0" --locked "${@:-HEAD}"
fi
revision=${2:-HEAD}
root=$(git rev-parse --show-toplevel)
web=${MOCK_WEB_DIR:-/home/ndivij/buildathon/sf-buildathon-2026/challenges/dossier/web}
port=${PROVER_PORT:-18200}
mock_port=${PROVER_MOCK_PORT:-18201}
if ((port < 18200 || port > 18299 || mock_port < 18200 || mock_port > 18299 || port == mock_port)); then
  echo 'Ports must be distinct and in 18200–18299' >&2; exit 2
fi
tag="prover-s1-$$"
tmp=$(mktemp -d)
cleanup() {
  timeout 20 docker rm -f "$tag-test" "$tag-default" "$tag-dest" "$tag-app" "$tag-web" >/dev/null 2>&1 || true
  timeout 20 docker network rm "$tag-net" >/dev/null 2>&1 || true
  timeout 20 docker image rm "$tag-app" "$tag-web" >/dev/null 2>&1 || true
  rm -rf "$tmp"
}
trap cleanup EXIT
git -C "$root" archive "$revision" stage-1 | tar -x -C "$tmp"
delivery_failed=0
if [[ ! -f "$tmp/stage-1/RUN.md" ]]; then
  echo 'R1.03: stage-1/RUN.md is missing' >&2
  delivery_failed=1
fi
cp -a "$web/corpus/sample" "$tmp/corpus"
python3 "$root/acceptance/stage-1/make_cases.py" "$tmp/corpus"
timeout 900 docker build -t "$tag-web" "$web"
timeout 900 docker build -t "$tag-app" "$tmp/stage-1"
timeout 20 docker network create --internal "$tag-net" >/dev/null
timeout 30 docker run -d --name "$tag-web" --network "$tag-net" --network-alias mock -e MOCK_ADMIN_TOKEN=prover-local -v "$tmp/corpus:/data/corpus:ro" -p "127.0.0.1:$mock_port:8080" "$tag-web" >/dev/null
started=$(python3 -c 'import time; print(time.time())')
timeout 30 docker run -d --name "$tag-app" --network "$tag-net" --network-alias app --cpus 2 --memory 3g -e PORT=8037 -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://mock:8080/nimble -p "127.0.0.1:$port:8037" "$tag-app" >/dev/null
timeout 30 docker run -d --name "$tag-dest" --network "$tag-net" --network-alias dest --cpus 2 --memory 3g -e PORT=8080 -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://mock:8080/nimble "$tag-app" >/dev/null
timeout 30 docker run -d --name "$tag-default" --network "$tag-net" --network-alias defaultapp --cpus 2 --memory 3g -e NIMBLE_API_KEY=local -e NIMBLE_BASE_URL=http://mock:8080/nimble "$tag-app" >/dev/null
timeout 900 docker run --name "$tag-test" --network "$tag-net" --entrypoint python3 -e PROVER_URL=http://app:8037 -e PROVER_DEST=http://dest:8080 -e PROVER_DEFAULT=http://defaultapp:8080 -e PROVER_MOCK=http://mock:8080 -e PROVER_CORPUS=/data/corpus -e "PROVER_START=$started" -v "$tmp/corpus:/data/corpus:ro" -v "$root/acceptance/stage-1:/acceptance:ro" "$tag-web" /acceptance/test_acceptance.py
exit "$delivery_failed"
