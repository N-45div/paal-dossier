#!/usr/bin/env bash
# Give every seat one shared Cognee memory over MCP, local or in Cognee Cloud.
#
#   bash cognee.sh local   # cognee-mcp + its own engine in Docker; needs ~/.cognee.env
#                          #   LLM_API_KEY=<OpenAI key>   COGNEE_MCP_AGENT_SCOPED=false
#   bash cognee.sh cloud   # cognee-mcp in Docker as a bridge to your Cognee Cloud tenant;
#                          #   needs ~/.cognee-cloud.env
#                          #   COGNEE_API_URL=https://tenant-<id>.aws.cognee.ai
#                          #   COGNEE_API_KEY=<key>   COGNEE_TENANT_ID=<id>
#   bash cognee.sh status
#
# Registers the server as MCP "cognee" (local, port 8765) or "cognee-cloud" (port 8766) at
# user scope for Claude Code and Codex, so it never writes a config file into a repository.
# Key files must be chmod 600; nothing here prints them.
set -euo pipefail
MODE="${1:-status}"

register() {  # name, url
  if command -v claude >/dev/null; then
    claude mcp remove --scope user "$1" >/dev/null 2>&1 || true
    claude mcp add --scope user --transport http "$1" "$2"
  fi
  if command -v codex >/dev/null; then
    codex mcp remove "$1" >/dev/null 2>&1 || true
    codex mcp add "$1" --url "$2"
  fi
}

wait_up() {  # port
  for _ in $(seq 1 60); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$1/mcp" || true)
    case "$code" in 200|307|400|405|406) echo "MCP on port $1 is up"; return 0 ;; esac
    sleep 5
  done
  echo "MCP on port $1 did not come up; see: docker logs $2" >&2; return 1
}

case "$MODE" in
  local)
    [ -f "$HOME/.cognee.env" ] || { echo "missing ~/.cognee.env" >&2; exit 1; }
    docker rm -f cognee >/dev/null 2>&1 || true
    docker run -d --name cognee --restart unless-stopped -e TRANSPORT_MODE=http \
      --env-file "$HOME/.cognee.env" -p 8765:8000 cognee/cognee-mcp:main >/dev/null
    wait_up 8765 cognee
    register cognee http://localhost:8765/mcp ;;
  cloud)
    [ -f "$HOME/.cognee-cloud.env" ] || { echo "missing ~/.cognee-cloud.env" >&2; exit 1; }
    set -a; . "$HOME/.cognee-cloud.env"; set +a
    docker rm -f cognee-cloud >/dev/null 2>&1 || true
    docker run -d --name cognee-cloud --restart unless-stopped -e TRANSPORT_MODE=http \
      -e API_URL="$COGNEE_API_URL" -e API_TOKEN="$COGNEE_API_KEY" \
      -e COGNEE_API_KEY="$COGNEE_API_KEY" -e COGNEE_TENANT_ID="${COGNEE_TENANT_ID:-}" \
      -p 8766:8000 cognee/cognee-mcp:main >/dev/null
    wait_up 8766 cognee-cloud
    register cognee-cloud http://localhost:8766/mcp ;;
  status)
    docker ps --filter name=cognee --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'
    command -v claude >/dev/null && claude mcp list 2>/dev/null | grep -i cognee || true ;;
  *) echo "usage: cognee.sh local|cloud|status" >&2; exit 2 ;;
esac
