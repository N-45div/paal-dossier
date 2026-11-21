---
name: cognee-memory
description: Give a team of coding agents (Band Desktop seats, Claude Code, Codex) one shared long-term memory with Cognee over MCP, either self-hosted in Docker or in Cognee Cloud. Use when someone wants agents to remember rulings, review findings or decisions across rooms, stages or context compaction, or asks to set up Cognee.
---

# Shared memory with Cognee

Cognee turns what agents store into a knowledge graph they can recall later. Every seat of
the factory gets the same memory, so a ruling the Lead makes in stage 1 or a defect the
Gatekeeper caught is still there in stage 4, after context compaction. The repository and
the room stay the source of truth; memory is the index of why things are the way they are.

## Choose a mode

| Mode | Where data lives | Needs | MCP name / port |
|---|---|---|---|
| local | Docker on this machine | an LLM key (OpenAI by default) | `cognee` / 8765 |
| cloud | your Cognee Cloud tenant | tenant URL, tenant id, API key | `cognee-cloud` / 8766 |

Both can run at once. Ports 8765/8766 stay clear of services on 8000 and 8080.

## Store keys without exposing them

Ask the person to type keys at a hidden prompt. Never place a key in a command line you
print, a repository, a mandate or a room message.

```bash
# local
read -rs K; printf 'LLM_API_KEY=%s\nCOGNEE_MCP_AGENT_SCOPED=false\n' "$K" > ~/.cognee.env; unset K
# cloud (values from the Cognee Cloud "API Keys" page)
read -rs K; printf 'COGNEE_API_URL=%s\nCOGNEE_TENANT_ID=%s\nCOGNEE_API_KEY=%s\n' \
  "https://tenant-<id>.aws.cognee.ai" "<tenant-id>" "$K" > ~/.cognee-cloud.env; unset K
chmod 600 ~/.cognee.env ~/.cognee-cloud.env 2>/dev/null
```

`COGNEE_MCP_AGENT_SCOPED=false` puts every seat in one dataset; without it each harness
writes its own.

## Start and register

```bash
bash "$KIT/setup/cognee.sh" local     # or: cloud
bash "$KIT/setup/cognee.sh" status
```

The script starts `cognee/cognee-mcp:main` (as a bridge to the tenant in cloud mode), waits
for `/mcp`, and registers it at **user** scope for Claude Code and Codex, so no `.mcp.json`
lands in a repository. Band Desktop Claude Code seats must use **Claude customizations: Use
my Claude setup** (context mode `local_config`) and **MCP servers: inherit yours** to see it.

## Verify with a round trip

```bash
claude -p "Use the cognee MCP tools to store 'memory check', then search for it. Reply OK or FAIL with the error." \
  --model claude-haiku-5-5 --allowedTools "mcp__cognee"
```

Cloud indexing is asynchronous: a search right after storing can say "still indexing";
retry after a few seconds.

## How seats should use it

Put this in a mandate (it is generic): *"If a shared memory tool is available, store each
ruling, each rejection and its fix, and each design decision as you make them, and recall
them before planning new work. If memory is unavailable, continue without it."* Tool calls
and stored text appear in the room log, so nothing secret goes into memory.
