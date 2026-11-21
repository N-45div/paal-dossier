#!/usr/bin/env bash
# Move the Codex seats of a running factory to another OpenAI model, without posting in the room.
#
#   bash switch-codex-model.sh <room-id> <model> <seat>...      e.g. ... gpt-6-luna ndivij2004/prover ndivij2004/gatekeeper
#
# Band fixes a seat's model at creation and has no command to change it, and a recreated seat
# gets a new room identity the other seats do not know. Instead this routes Codex through
# setup/model-proxy.py (started here if needed), which rewrites the model on every request:
# it writes the target model, adds a `paal` provider to ~/.codex/config.toml, then restarts
# each seat once it has been quiet for three minutes so it picks up the provider and resumes
# its pending work. It then checks the proxy log for rewritten requests; if none arrive
# within 20 minutes it reverts the provider so the seats keep working on their old model.
set -uo pipefail
ROOM="$1"; MODEL="$2"; shift 2; SEATS=("$@")
KIT="$(cd "$(dirname "$0")" && pwd)"; PORT="${MODEL_PROXY_PORT:-8791}"
CFG="$HOME/.codex/config.toml"; LOG="$HOME/model-proxy.log"
log() { echo "$(date -u +%FT%TZ) $*"; }
seat_idle() {
  local name last; name=$(echo "${1##*/}" | sed -E 's/-/ /; s/\b(.)/\u\1/g')
  last=$(band room messages "$ROOM" --json 2>/dev/null \
         | jq -r --arg n "$name" '[.messages[] | select(.sender_name==$n) | .inserted_at] | max // empty')
  [ -z "$last" ] || [ $(( $(date +%s) - $(date -d "$last" +%s) )) -ge 180 ]
}

pgrep -f "model-proxy.py $PORT" >/dev/null \
  || { nohup python3 "$KIT/model-proxy.py" "$PORT" >> "$LOG" 2>&1 < /dev/null & sleep 2; }
curl -s -m 5 -o /dev/null "http://127.0.0.1:$PORT/" || { log "proxy did not start"; exit 1; }
echo "$MODEL" > "$HOME/.paal-model-target"

cp "$CFG" "$CFG.before-switch"
if ! grep -q '^model_provider *= *"paal"' "$CFG"; then
  { printf 'model_provider = "paal"\n'; cat "$CFG.before-switch"
    printf '\n[model_providers.paal]\nname = "paal"\nbase_url = "http://127.0.0.1:%s/v1"\nwire_api = "responses"\nrequires_openai_auth = true\n' "$PORT"
  } > "$CFG"
fi
log "provider armed: Codex -> 127.0.0.1:$PORT, model -> $MODEL"

mark=$(wc -l < "$LOG")
for s in "${SEATS[@]}"; do
  for _ in $(seq 1 15); do seat_idle "$s" && break; sleep 120; done
  band restart --as "$s" >/dev/null 2>&1 && log "restarted $s"
done

for _ in $(seq 1 20); do
  n=$(tail -n +"$((mark + 1))" "$LOG" | grep -c -- "-> $MODEL")
  [ "$n" -gt 0 ] && { log "verified: $n request(s) rewritten to $MODEL"; exit 0; }
  sleep 60
done
log "no seat traffic through the proxy after 20 minutes -> reverting the provider"
cp "$CFG.before-switch" "$CFG"
for s in "${SEATS[@]}"; do band restart --as "$s" >/dev/null 2>&1 && log "restarted $s on its old model"; done
exit 2
