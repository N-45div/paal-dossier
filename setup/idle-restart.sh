#!/usr/bin/env bash
# Restart every seat when the whole room has gone idle, without posting anything in it.
#
#   bash idle-restart.sh <room-id> <seat>...       e.g. ... ndivij2004/lead ndivij2004/builder-a ...
#
# A seat acts only when a message mentions it, so a band can stop with every seat idle and no
# message left to answer: a builder that settled its last message without finishing its
# package, and a coordinator that believes the builder is still working. A restart makes each
# seat resume its own pending work and open tasks. This sends nothing into the room, so it is
# not steering. When no seat has done anything for IDLE_MIN minutes (default 20), the script
# restarts the seats one by one, at most once every GAP_MIN minutes (default 30).
set -uo pipefail
ROOM="$1"; shift; SEATS=("$@")
IDLE=$(( ${IDLE_MIN:-20} * 60 )); GAP=$(( ${GAP_MIN:-30} * 60 )); last_restart=0
log() { echo "$(date -u +%FT%TZ) $*"; }
while :; do
  newest=$(band room messages "$ROOM" --json 2>/dev/null | jq -r '[.messages[].inserted_at] | max // empty')
  if [ -n "$newest" ]; then
    idle=$(( $(date +%s) - $(date -d "$newest" +%s) ))
    if [ "$idle" -ge "$IDLE" ] && [ $(( $(date +%s) - last_restart )) -ge "$GAP" ]; then
      log "room idle ${idle}s (last activity $newest) -> restarting all seats"
      for s in "${SEATS[@]}"; do band restart --as "$s" >/dev/null 2>&1 && log "restarted $s"; sleep 5; done
      last_restart=$(date +%s)
    fi
  fi
  sleep 60
done
