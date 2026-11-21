#!/usr/bin/env bash
# Per-user tooling for a factory machine. Run inside Linux/WSL as your normal user (no sudo).
#
#   bash bootstrap-user.sh [workspace-root] [factory-kit-source]
#
# Installs Node 22 + Codex CLI (via nvm), Claude Code, clones the kickoff package, builds its
# Python virtual environment with the harness and Chromium, and copies the factory kit into the
# workspace if it is not there yet. Re-running it is safe. Browser system libraries need root
# once: <workspace>/sf-buildathon-2026/.venv/bin/python -m playwright install-deps chromium
set -euo pipefail

WS="${1:-$HOME/buildathon}"
KIT_SRC="${2:-}"
mkdir -p "$WS/band-work/checks"

echo "== Node 22 and Codex CLI =="
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] || curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"
nvm install 22 >/dev/null
command -v codex >/dev/null 2>&1 || npm install -g @openai/codex
echo "codex: $(codex --version 2>/dev/null || echo installed)"

echo "== Claude Code =="
export PATH="$HOME/.local/bin:$PATH"
command -v claude >/dev/null 2>&1 || curl -fsSL https://claude.ai/install.sh | bash
echo "claude: $(claude --version 2>/dev/null || echo installed)"

echo "== Kickoff package and harness =="
cd "$WS"
[ -d sf-buildathon-2026 ] || git clone -q https://github.com/band-ai/sf-buildathon-2026.git
cd sf-buildathon-2026
echo "kickoff at $(git log -1 --format='%h %cd')"
[ -d .venv ] || python3.12 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r harness/requirements.txt
python -m playwright install chromium
python -m harness --help >/dev/null && echo "harness OK"

echo "== Factory kit =="
if [ -n "$KIT_SRC" ] && [ ! -e "$WS/factory-kit" ]; then
  cp -r "$KIT_SRC" "$WS/factory-kit"
  echo "copied kit to $WS/factory-kit"
else
  echo "kit: ${WS}/factory-kit $( [ -e "$WS/factory-kit" ] && echo present || echo 'not copied (no source given)')"
fi
echo "== bootstrap done =="
