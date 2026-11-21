#!/usr/bin/env bash
# Paal Brain: one long-term memory for an org of Band agent factories, in Cognee Cloud.
#
#   bash brain.sh remember <dataset> <file>...   # ingest lessons, retros, decisions
#   bash brain.sh scout    <dataset> <url>...    # Nimble fetches each page as markdown,
#                                                #   Cognee indexes it (key stays on this host)
#   bash brain.sh recall   "<question>" [dataset]
#
# Seats reach the same memory through the cognee-cloud MCP server (setup/cognee.sh cloud), so
# every factory in the org recalls what earlier factories learned and the documentation that
# was scouted for it, without ever holding the Nimble or Cognee keys.
# Needs ~/.cognee-cloud.env (COGNEE_API_URL, COGNEE_TENANT_ID, COGNEE_API_KEY) and, for scout,
# ~/.nimble.env (NIMBLE_API_KEY). Both chmod 600; nothing here prints them.
set -euo pipefail
CMD="${1:-}"; shift || true
set -a; . "$HOME/.cognee-cloud.env"; set +a
auth=(-H "X-Api-Key: $COGNEE_API_KEY" -H "X-Tenant-Id: ${COGNEE_TENANT_ID:-}")

remember() {  # dataset, file
  local code
  code=$(curl -s -o /tmp/brain-remember.json -w '%{http_code}' -X POST "$COGNEE_API_URL/api/v1/remember" \
    "${auth[@]}" -F "data=@$2" -F "datasetName=$1")
  echo "remember $(basename "$2") -> $1: HTTP $code $(jq -c '.status // .message // empty' /tmp/brain-remember.json 2>/dev/null | head -c 120)"
  rm -f /tmp/brain-remember.json
}

case "$CMD" in
  remember)
    ds="${1:?dataset}"; shift
    for f in "$@"; do remember "$ds" "$f"; done ;;
  scout)
    ds="${1:?dataset}"; shift
    set -a; . "$HOME/.nimble.env"; set +a
    mkdir -p /tmp/brain-scout
    for url in "$@"; do
      slug=$(printf '%s' "$url" | sed -E 's#^https?://##; s#[^A-Za-z0-9]+#-#g' | cut -c1-80)
      out="/tmp/brain-scout/$slug.md"
      code=$(curl -s -o /tmp/brain-nimble.json -w '%{http_code}' -X POST https://sdk.nimbleway.com/v2/extract \
        -H "Authorization: Bearer $NIMBLE_API_KEY" -H 'Content-Type: application/json' \
        -d "{\"url\": \"$url\", \"formats\": [\"markdown\"]}")
      if [ "$code" != 200 ]; then echo "scout $url: Nimble HTTP $code"; continue; fi
      { echo "# Source: $url"; echo "Fetched by Nimble on $(date -u +%F) for the Paal brain."; echo;
        jq -r '.data.markdown // .data.content // .data // ""' /tmp/brain-nimble.json; } > "$out"
      echo "scout $url: $(wc -c < "$out") bytes"
      remember "$ds" "$out"
    done
    rm -f /tmp/brain-nimble.json ;;
  recall)
    q="${1:?question}"; ds="${2:-}"
    body=$(jq -n --arg q "$q" --arg d "$ds" '{query: $q, topK: 8} + (if $d == "" then {} else {datasets: [$d]} end)')
    curl -s -X POST "$COGNEE_API_URL/api/v1/recall" "${auth[@]}" -H 'Content-Type: application/json' -d "$body" \
      | jq -r 'if type=="array" then .[] | (.text // .search_result // .) | tostring else (.answer // .result // .) | tostring end' \
      | head -c 4000; echo ;;
  *) echo "usage: brain.sh remember <dataset> <file>... | scout <dataset> <url>... | recall \"<question>\" [dataset]" >&2; exit 2 ;;
esac
