# Safety Gate for Adopting Reel-Discovered Tools

A Reel is a lead, not a review. Nothing gets installed because a video said so.

## Step 1 — Verify the claim

- Find the primary source: official repo, docs, or paper. Search snippets and
  screenshots are not evidence.
- Record: repo URL, license, last-commit date, what it actually does.
- Label: `verified / partly verified / unsupported / misleading / unresolved`.

## Step 2 — Static audit (before any install)

Shallow clone (`git clone --depth 1 --no-tags`), then scan for:

| Signal | Why it matters |
|---|---|
| `os.environ` / `.env` / dotenv | credential access |
| `requests` / `httpx` / `fetch` / sockets | network egress, exfiltration |
| `subprocess` / `child_process` / `eval` / `exec` | code execution |
| install scripts, `postinstall`, `curl \| sh` | supply-chain hooks |
| cookies / sessions / OAuth flows | account takeover surface |
| telemetry / analytics endpoints | silent data sharing |
| publish/upload/post APIs | outbound side effects |
| writes to agent config (MCP, skills dirs) | self-modifying agent |

## Step 3 — Gate decision

**Auto-adopt is allowed only when ALL are true:**

- Pure prompt/workflow skill (e.g. a single `SKILL.md`)
- No scripts, no code execution, no network, no env reads
- No MCP/provider/config writes
- License permits use

**Everything else is *proposed*:** record repo, license, what it would add,
blocking reason, and what a safe evaluation would look like (disposable
profile, disabled cloud routes, no auto-config writes). A human approves or
rejects proposals.

**Always reject for agent use:** credential/session harvesters, bulk
downloaders of protected content, deepfake/impersonation tools, provider
routers that reintroduce excluded providers, anything that publishes
externally without a review step.

## Step 4 — Record

Append dated findings with source URLs and verdicts to the research log.
Never record credential values, session contents, or tokens.
