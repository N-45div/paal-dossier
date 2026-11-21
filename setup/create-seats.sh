#!/usr/bin/env bash
# Create the five factory seats as Band-owned headless runtimes (Band Desktop must be running).
#
#   bash create-seats.sh rehearsal          # cheap models, for practice runs
#   bash create-seats.sh judged             # the models the submitted run uses
#   DRY_RUN=1 bash create-seats.sh judged   # probe each runtime, create nothing
#   SESSION_SUFFIX=-v2 bash create-seats.sh judged   # recreate after removing earlier seats
#
# Each seat's instructions are live-linked to mandates/<seat>.md, so editing a mandate changes
# the seat on its next start. Override any model with LEAD_MODEL, BUILDER_MODEL, CODEX_MODEL.
set -euo pipefail

MODE="${1:-rehearsal}"
WS="${WS:-$HOME/buildathon}"
KIT="${KIT:-$WS/factory-kit}"

case "$MODE" in
  judged)
    LEAD_MODEL="${LEAD_MODEL:-claude-sonnet-5-5}";     LEAD_EFFORT="${LEAD_EFFORT:-high}"
    BUILDER_MODEL="${BUILDER_MODEL:-claude-haiku-5-5}"; BUILDER_EFFORT="${BUILDER_EFFORT:-medium}"
    CODEX_MODEL="${CODEX_MODEL:-gpt-6.1-terra}";     CODEX_EFFORT="${CODEX_EFFORT:-medium}" ;;
  claude)   # every seat on Claude Code, for a single Claude subscription
    LEAD_MODEL="${LEAD_MODEL:-claude-sonnet-5-5}";     LEAD_EFFORT="${LEAD_EFFORT:-high}"
    BUILDER_MODEL="${BUILDER_MODEL:-claude-haiku-5-5}"; BUILDER_EFFORT="${BUILDER_EFFORT:-medium}"
    PROVER_MODEL="${PROVER_MODEL:-claude-haiku-5-5}";   GATE_MODEL="${GATE_MODEL:-claude-sonnet-5-5}"
    REVIEW_EFFORT="${REVIEW_EFFORT:-medium}" ;;
  rehearsal)
    LEAD_MODEL="${LEAD_MODEL:-claude-haiku-5-5}";    LEAD_EFFORT="${LEAD_EFFORT:-medium}"
    BUILDER_MODEL="${BUILDER_MODEL:-claude-haiku-5-5}"; BUILDER_EFFORT="${BUILDER_EFFORT:-medium}"
    CODEX_MODEL="${CODEX_MODEL:-gpt-6-luna}";        CODEX_EFFORT="${CODEX_EFFORT:-low}" ;;
  *) echo "usage: create-seats.sh rehearsal|judged|claude" >&2; exit 2 ;;
esac

# Band Desktop 0.4.18 on Linux launches ~/.local/share/jam/daemon/jam as the Claude seats'
# message relay but only installs jamd there. Without it every Claude Code seat fails its
# startup gate ("could not load Band's disposition MCP relay"). Link the packaged binary.
JAM_RELAY="$HOME/.local/share/jam/daemon/jam"
if [ ! -x "$JAM_RELAY" ] && [ -x /usr/bin/jam ]; then
  mkdir -p "$(dirname "$JAM_RELAY")" && ln -sf /usr/bin/jam "$JAM_RELAY"
  echo "linked missing Band relay: $JAM_RELAY -> /usr/bin/jam"
fi

claude_seat() {  # name, handle, model, effort, description
  local cmd=(band agent create --session "seat-$2${SESSION_SUFFIX:-}" --json --name "$1" --description "$5"
             --cwd "$WS" --transport claude-code-cli --runtime-auth inherit
             --runtime-model "$3" --runtime-effort "$4"
             --claude-permission-mode auto --claude-context-mode local_config)
  run_seat "$1" "$2" "${cmd[@]}"
}

codex_seat() {   # name, handle, description
  local cmd=(band agent create --session "seat-$2${SESSION_SUFFIX:-}" --json --name "$1" --description "$3"
             --cwd "$WS" --transport codex-app-server --runtime-auth inherit
             --runtime-model "$CODEX_MODEL" --runtime-effort "$CODEX_EFFORT"
             --runtime-approval never --runtime-sandbox danger-full-access)
  run_seat "$1" "$2" "${cmd[@]}"
}

run_seat() {     # name, handle, command...
  local name="$1" handle="$2"; shift 2
  local cmd=("$@")
  if [ -n "${DRY_RUN:-}" ]; then cmd+=(--dry-run); else cmd+=(--instructions-file "$KIT/mandates/$handle.md"); fi
  echo "=== $name ($handle)"
  "${cmd[@]}" | jq -c '{ok, error, created: (.created | if . then {id: (.id // .agent_id), handle: (.handle // .agentHandle)} else null end)}' 2>/dev/null \
    || "${cmd[@]}"
}

claude_seat "Lead"      lead      "$LEAD_MODEL"    "$LEAD_EFFORT" \
  "Plans the work, keeps the requirements ledger, rules on ambiguity and freezes each stage. Never writes product code."
claude_seat "Builder A" builder-a "$BUILDER_MODEL" "$BUILDER_EFFORT" \
  "Implements assigned work packages in its own worktree and hands off exact commits. Never accepts its own work."
claude_seat "Builder B" builder-b "$BUILDER_MODEL" "$BUILDER_EFFORT" \
  "Implements assigned work packages in its own worktree and hands off exact commits. Never accepts its own work."
PROVER_DESC="Writes independent black-box acceptance tests from the specification and reports failing requirements. Never reads product code first."
GATE_DESC="The only seat that accepts and merges work: rebuilds exact commits, runs every check, tests the tests. Never fixes code."
if [ "$MODE" = claude ]; then
  claude_seat "Prover"     prover     "$PROVER_MODEL" "$REVIEW_EFFORT" "$PROVER_DESC"
  claude_seat "Gatekeeper" gatekeeper "$GATE_MODEL"   "$REVIEW_EFFORT" "$GATE_DESC"
  echo "Models: lead=$LEAD_MODEL/$LEAD_EFFORT builders=$BUILDER_MODEL/$BUILDER_EFFORT prover=$PROVER_MODEL gatekeeper=$GATE_MODEL/$REVIEW_EFFORT"
else
  codex_seat "Prover"     prover     "$PROVER_DESC"
  codex_seat "Gatekeeper" gatekeeper "$GATE_DESC"
  echo "Models: lead=$LEAD_MODEL/$LEAD_EFFORT builders=$BUILDER_MODEL/$BUILDER_EFFORT codex=$CODEX_MODEL/$CODEX_EFFORT"
fi
