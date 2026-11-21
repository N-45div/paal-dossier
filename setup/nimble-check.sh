#!/usr/bin/env bash
# Check a Nimble key with one cheap search (depth "lite": title, URL, snippet).
#
#   bash nimble-check.sh [query]        # reads NIMBLE_API_KEY from ~/.nimble.env
#
# Store the key once, hidden:  read -rs K; printf 'NIMBLE_API_KEY=%s\n' "$K" > ~/.nimble.env;
#                              chmod 600 ~/.nimble.env; unset K
# The key is for live runs you start yourself. Never give it to a factory seat: everything a
# seat runs lands in the room log.
set -euo pipefail
QUERY="${1:-runway.com}"
[ -f "$HOME/.nimble.env" ] || { echo "missing ~/.nimble.env" >&2; exit 1; }
set -a; . "$HOME/.nimble.env"; set +a
BASE="${NIMBLE_BASE_URL:-https://sdk.nimbleway.com}"
code=$(curl -s -o /tmp/nimble-check.json -w '%{http_code}' -X POST "$BASE/v2/search" \
  -H "Authorization: Bearer $NIMBLE_API_KEY" -H 'Content-Type: application/json' \
  -d "{\"query\": \"$QUERY\", \"max_results\": 3, \"search_depth\": \"lite\"}")
echo "Nimble search HTTP $code"
python3 - <<'P'
import json
d = json.load(open("/tmp/nimble-check.json"))
rows = d.get("results") or d.get("data") or []
for r in rows[:3] if isinstance(rows, list) else []:
    print("-", r.get("title"), "|", r.get("url"))
if not rows: print(str(d)[:300])
P
rm -f /tmp/nimble-check.json
[ "$code" = 200 ]
