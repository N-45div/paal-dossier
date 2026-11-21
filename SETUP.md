# Factory setup checklist

Everything runs inside WSL2 Ubuntu, whose disk lives on `D:\WSL\Ubuntu-24.04`. Paths below
use `~/buildathon` as the workspace root. Keys never go into a repository, a mandate or a
room message.

## 1. WSL and Ubuntu on D (admin PowerShell)

```powershell
wsl --install --no-distribution          # then reboot
wsl --update
wsl --install -d Ubuntu-24.04 --location D:\WSL\Ubuntu-24.04
# if --location is rejected:
#   wsl --install -d Ubuntu-24.04; wsl --shutdown; wsl --manage Ubuntu-24.04 --move D:\WSL\Ubuntu-24.04
```

Before installing, create `%USERPROFILE%\.wslconfig` so swap also lives on D and WSL
leaves RAM for Windows (adjust `memory` to about two thirds of your RAM):

```ini
[wsl2]
memory=10GB
swap=8GB
swapFile=D:\\WSL\\swap.vhdx

[experimental]
sparseVhd=true
```

## 2. Tools inside Ubuntu

```bash
sudo apt update && sudo apt install -y git curl build-essential python3.12-venv util-linux
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER
# PowerShell: wsl --shutdown, then reopen Ubuntu; check: docker run --rm hello-world
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash   # reopen shell
nvm install 22 && npm install -g @openai/codex
curl -fsSL https://claude.ai/install.sh | bash
```

## 3. Sign the coding agents in

```bash
claude            # /login -> Anthropic Console account (bills the API credits)
read -rs K && printf %s "$K" | codex login --with-api-key; unset K   # paste the OpenAI key
```

## 4. Kickoff package and harness

```bash
mkdir -p ~/buildathon && cd ~/buildathon
git clone https://github.com/band-ai/sf-buildathon-2026.git
cd sf-buildathon-2026 && python3.12 -m venv .venv && . .venv/bin/activate
python -m pip install -r harness/requirements.txt
python -m playwright install --with-deps chromium
python -m harness --help
```

## 5. Factory kit into WSL

```bash
cp -r /mnt/c/Users/<windows-user>/band-hackathon ~/buildathon/factory-kit   # or git clone the kit
```

## 6. Band Desktop (Linux build, shown on Windows through WSLg)

```bash
cd /tmp && curl -fLO https://downloads.band.ai/desktop/latest/linux/jam-amd64.deb
sudo apt install -y ./jam-amd64.deb
band-desktop &     # blank window? WEBKIT_DISABLE_DMABUF_RENDERER=1 band-desktop &
```

Setup wizard: sign in (if no browser opens, **Copy link** and paste it into a Windows
browser); turn on **Claude Code** and **Codex**; turn **off** the Express starter team; turn
on **Run Band in the background**. Then `band doctor` must show every check `[ok]`.

**Settings -> Runtime**

| Setting | Value | Why |
|---|---|---|
| Human approval wait | Deny after 5 minutes | A stray permission ask resolves itself instead of waiting for you |
| Question timeout (seconds) | 300 | Same, for questions |
| Room activity feed | Tool calls | The room log is the teamwork evidence |
| Stop idle agents after (seconds) | 1800 | Codex seats keep context while builds run |
| Resume thread on wake | On | |

## 7. Shared memory (Cognee, optional but planned)

```bash
read -rs K; printf 'LLM_API_KEY=%s\nCOGNEE_MCP_AGENT_SCOPED=false\n' "$K" > ~/.cognee.env; unset K
chmod 600 ~/.cognee.env
bash ~/buildathon/factory-kit/setup/cognee.sh local     # or: cloud (see skills/cognee-memory)
```

Port 8765 keeps clear of the service (8000) and mock web (8080). Memory contents and tool
calls appear in the public room log, so nothing secret goes into memory.

## 8. Create the five seats (Agents -> New agent)

Every seat: **Working directory** `/home/<you>/buildathon`; **Choose instructions file** ->
`~/buildathon/factory-kit/mandates/<seat>.md`; run **Test runtime** before saving.

| Name | Handle | Runtime | Model: rehearsal / judged run | Permissions |
|---|---|---|---|---|
| Lead | `lead` | Claude Code | Haiku 5.5 / Opus 5.5 | Permission mode **Auto** |
| Builder A | `builder-a` | Claude Code | Haiku 5.5 / Sonnet 5.5 | **Auto** |
| Builder B | `builder-b` | Claude Code | Haiku 5.5 / Sonnet 5.5 | **Auto** |
| Prover | `prover` | Codex | cheap Codex model / Codex default | Approval **Never ask**, tool access **Full access** |
| Gatekeeper | `gatekeeper` | Codex | cheap Codex model / Codex default | **Never ask**, **Full access** |

Claude Code seats: **Claude customizations** = Use my Claude setup; **MCP servers** = inherit
yours (needed for Cognee). After choosing models, copy the exact model id and effort into the
`Model:` and `Effort:` lines of each mandate. If Band shows handles different from the table,
update the roster table in all five mandates to match exactly.

## 9. Each run

```bash
bash ~/buildathon/factory-kit/setup/prepare-result-repo.sh ~/buildathon/band-work/toy-result   # rehearsal
bash ~/buildathon/factory-kit/setup/prepare-result-repo.sh ~/buildathon/band-work/result       # judged run
mkdir -p ~/buildathon/band-work/checks
```

Then: **New room** -> add all five seats -> paste the prompt from `DISPATCH.md`. In a
practice room only, first check `@handle` round trips (for example ask `@lead` to ping
`@builder-a` and report the reply).

## 10. Budget

| Model | Input $/M | Output $/M | Cached input $/M |
|---|---|---|---|
| Claude Opus 5.5 | 4.00 | 20.00 | 0.20 |
| Claude Sonnet 5.5 | 2.00 | 10.00 | 0.10 |
| Claude Haiku 5.5 | 0.10 | 0.50 | (prompts over 100K tokens: 0.50 / 2.50) |

Rehearse on Haiku. Run one Dossier stage-1 practice on the judged-run models and read
**Analytics -> Usage & Cost** for the real cost, then make sure the credit left covers four
stages with margin before starting the judged run. Running out mid-run stalls it, and a
second dispatch counts as a rerun.

## 11. Nimble key (end of the week only)

Sign up at https://online.nimbleway.com/signup -> **Settings -> API Keys**. You use it
yourself, after the judged run, to make `dossier-runway.com.json` with the participant
guide's commands. Never give it to a seat.
