# Satellite CLI: Bun/TypeScript Rewrite

## Why

The original Satellite is a Python Textual TUI — great for humans, but agents can't drive it. An AI agent that wants to run a benchmark, check scores, or submit to the leaderboard has to simulate keypresses in a terminal UI. That's fragile and slow.

The Bun/TypeScript CLI replaces the interactive frontend with structured JSON output. Every command returns machine-parseable data. The `run` command streams JSONL progress events. An agent can now:

```bash
satellite run --benchmark teleqna --model openai/gpt-4o --limit 5 | while read line; do
  echo "$line" | jq -r '.event'
done
```

## What Changed

**Replaced**: Python Textual TUI (interactive screens, modals, key bindings)

**With**: Bun/TypeScript CLI (6 commands, JSON/JSONL output, zero interactivity)

**Kept**: The `inspect eval` Python CLI as the only Python dependency. Everything else — parquet building, GitHub API, leaderboard fetching, config management — is reimplemented in TypeScript using Bun built-ins.

## Architecture

```
cli/
├── package.json              # Single runtime dep: @dsnp/parquetjs
├── tsconfig.json             # Strict mode, ESNext target
└── src/
    ├── index.ts              # Entry point + CLI arg parser + command router
    ├── types/
    │   └── index.ts          # All shared interfaces (CLIArgs, JobStatus, RunEvent, etc.)
    ├── utils/
    │   ├── errors.ts         # SatelliteError class + exitWithError()
    │   └── output.ts         # emitJSON() for one-shot, emitEvent() for JSONL streaming
    ├── commands/
    │   ├── benchmarks.ts     # List available benchmarks
    │   ├── status.ts         # List/query job status
    │   ├── results.ts        # View eval scores for completed jobs
    │   ├── leaderboard.ts    # Fetch rankings from HuggingFace
    │   ├── run.ts            # Run an evaluation (streaming JSONL)
    │   └── submit.ts         # Submit results to leaderboard via GitHub PR
    └── services/
        ├── benchmark-registry.ts   # 7 hardcoded telecom benchmarks
        ├── config-manager.ts       # .env parsing + eval_settings.json + provider detection
        ├── eval-log-reader.ts      # Parse Inspect AI JSON log files
        ├── eval-runner.ts          # Bun.spawn inspect eval + fs.watch progress tracking
        ├── github-client.ts        # GitHub REST API (Git Data API, no git CLI)
        ├── job-manager.ts          # Job directory scanning + status aggregation
        ├── leaderboard-client.ts   # Fetch + parse CSV from HuggingFace datasets
        ├── parquet-builder.ts      # Build single-row leaderboard parquet files
        └── submit-service.ts       # Orchestrate eligibility + parquet + GitHub PR
```

**19 TypeScript files total.** One runtime dependency (`@dsnp/parquetjs`). Everything else uses Bun/Node built-ins: `fetch()`, `Bun.spawn()`, `fs.watch()`, `node:fs`, `node:path`.

## Commands

### `satellite benchmarks`

Lists all 7 telecom benchmarks with ID, name, sample count, and module path.

```bash
$ satellite benchmarks | jq '.[0]'
{
  "id": "teleqna",
  "name": "TeleQnA",
  "samples": 1000,
  "modulePath": "evals.teleqna.teleqna"
}
```

### `satellite status [--job JOB_ID] [--jobs-dir PATH]`

Lists all jobs or shows detail for a specific job. Jobs are discovered from the filesystem (`jobs/` directory).

```bash
$ satellite status
[
  { "jobId": "job_20260304_143000", "status": "completed", "totalEvals": 7, ... },
  { "jobId": "job_20260303_091500", "status": "running", "completedEvals": 3, ... }
]
```

### `satellite results --job JOB_ID`

Returns accuracy scores and sample counts for a completed job, broken down by model and benchmark.

```bash
$ satellite results --job job_20260304_143000
{
  "jobId": "job_20260304_143000",
  "status": "completed",
  "results": { "openai/gpt-4o": { "teleqna": 0.852, "telelogs": 0.82, ... } },
  "sampleCounts": { "openai/gpt-4o": { "teleqna": 1000, "telelogs": 100, ... } }
}
```

### `satellite leaderboard`

Fetches the current leaderboard from the GSMA/leaderboard HuggingFace dataset. Scores are displayed as percentages (0-100).

```bash
$ satellite leaderboard | jq '.[0]'
{
  "model": "gemini-3.1-pro-preview",
  "provider": "Google",
  "scores": {
    "teleqna": { "score": 85.2, "stderr": 1.12 },
    "telelogs": { "score": 82, "stderr": 3.86 },
    ...
  }
}
```

### `satellite run --benchmark ID --model MODEL [--limit N] [--jobs-dir PATH]`

Runs an evaluation via `inspect eval` subprocess. Streams JSONL progress events to stdout.

```bash
$ satellite run --benchmark teleqna --model openai/gpt-4o --limit 5
{"event":"started","jobId":"job_20260304_143000","benchmark":"teleqna","model":"openai/gpt-4o"}
{"event":"progress","jobId":"job_20260304_143000","completed":2,"total":5}
{"event":"progress","jobId":"job_20260304_143000","completed":5,"total":5}
{"event":"completed","jobId":"job_20260304_143000","score":0.8,"samples":5}
```

Exit codes: `0` success, `1` error, `2` cancelled (SIGINT).

### `satellite submit --job JOB_ID --model MODEL [--token TOKEN]`

Submits results to the GSMA leaderboard via GitHub PR. Builds a parquet file, uploads via Git Data API, creates a PR.

```bash
$ satellite submit --job job_20260304_143000 --model openai/gpt-4o --token ghp_...
{
  "prUrl": "https://github.com/gsma-labs/leaderboard/pull/42",
  "branch": "submit/openai_gpt-4o/20260304_143000",
  "model": "openai/gpt-4o"
}
```

## Key Implementation Details

### Benchmark Registry

7 telecom LLM benchmarks, hardcoded from the Python `registry.py`:

| ID | Name | Samples | HF Column | Module Path |
|----|------|---------|-----------|-------------|
| `teleqna` | TeleQnA | 1000 | `teleqna` | `evals.teleqna.teleqna` |
| `telelogs` | TeleLogs | 100 | `telelogs` | `evals.telelogs.telelogs` |
| `telemath` | TeleMath | 100 | `telemath` | `evals.telemath.telemath` |
| `teletables` | TeleTables | 100 | `teletables` | `evals.teletables.teletables` |
| `three_gpp` | 3GPP | 100 | `3gpp_tsg` | `evals.three_gpp.three_gpp` |
| `oranbench` | ORANBench | 150 | `oranbench` | `evals.oranbench.oranbench` |
| `srsranbench` | srsRANBench | 150 | `srsranbench` | `evals.srsranbench.srsranbench` |

**Critical detail**: Parquet columns and CSV columns use benchmark `id` (e.g., `three_gpp`), NOT `hfColumn` (e.g., `3gpp_tsg`). The `hfColumn` field exists for historical compatibility but is not used in the CLI.

### Eval Runner

Spawns `inspect eval` directly as a subprocess using `Bun.spawn()`:

```
inspect eval evals.teleqna.teleqna \
  --model openai/gpt-4o \
  --log-dir jobs/{jobId}/{model} \
  --epochs 1 --max-connections 10 \
  --log-format json --display none \
  --log-realtime --log-samples
```

Progress tracking uses a dual strategy:
1. **`fs.watch()`** on the log directory — triggers on log file creation/modification
2. **2-second polling fallback** — because `fs.watch` is unreliable on some platforms (Docker, NFS)

When either fires, it reads eval log headers to extract `completedSamples / totalSamples` and emits a JSONL progress event.

Cancellation: SIGINT is forwarded to the subprocess. A `cancelled` marker file is written so `job-manager` knows the job was cancelled.

### Leaderboard Client

Fetches CSV directly from HuggingFace:
```
https://huggingface.co/datasets/GSMA/leaderboard/resolve/main/leaderboard_scores.csv
```

This eliminates the `huggingface_hub` Python dependency. The CSV parser handles double-quoted fields containing commas (score values like `"[0.852, 0.0112]"`).

Score parsing: `"[0.852, 0.0112]"` -> `JSON.parse()` -> first element * 100 = percentage.

### Parquet Builder

Uses `@dsnp/parquetjs` to create single-row parquet files matching the HuggingFace leaderboard schema:

- Schema: `model` (UTF8), `provider` (UTF8), `[benchmark_id columns]` (UTF8, optional), `date` (UTF8)
- Score format: `"[0.852000, 0.012000]"` — string-encoded `[score, stderr]` at 0-1 scale, 6 decimal places
- Writes to a temp file via `ParquetWriter.openFile()`, reads back as Buffer, then deletes

### GitHub Client

Port of the Python `GitHubClient` using `fetch()`. Nine-step Git Data API flow for git-less file uploads:

1. `GET /user` — authenticate
2. `GET /repos/{repo}` — check push access
3. `GET /repos/{repo}/git/ref/heads/main` — get SHA
4. `POST /repos/{repo}/git/refs` — create branch
5. `POST /repos/{repo}/git/blobs` — upload base64 parquet
6. `POST /repos/{repo}/git/trees` — create tree
7. `POST /repos/{repo}/git/commits` — create commit
8. `PATCH /repos/{repo}/git/refs/heads/{branch}` — update ref
9. `POST /repos/{repo}/pulls` — create PR

Fork workflow: If the user lacks push access, forks the repo first, pushes to the fork, and creates a cross-repo PR.

### Config Manager

- **Eval settings**: `~/.satellite/eval_settings.json` — epochs, max_connections, limit, logSamples
- **Environment**: `.env` file with `KEY=VALUE` format, handles single/double-quoted values
- **Permissions**: `.env` written with `0o600` (user-only read/write)
- **Provider detection**: 20+ provider prefixes recognized (openai, anthropic, google, bedrock, vertex, etc.)
- **Proxy stripping**: Removes proxy prefixes (openrouter, bedrock, vertex, azureai) from model strings

### Job Manager

Discovers jobs from filesystem:
1. Looks for `job_*` directories in the jobs dir
2. Loads manifest from `job-manifest.json` (or legacy `eval-set.json`)
3. Discovers model subdirectories containing eval logs
4. Aggregates status using priority: running(0) > error(1) > cancelled(2) > success(3)
5. If fewer evals found than manifest expects AND all observed are completed -> still "running"

Jobs directory resolution: `--jobs-dir` flag > `SATELLITE_JOBS_DIR` env > `./jobs` > `../jobs`

### Error Handling

All errors output as JSON on stderr:
```json
{"error": "Job not found: job_123", "code": "NOT_FOUND"}
```

Error codes: `EVAL_ERROR`, `PARSE_ERROR`, `CONFIG_ERROR`, `SUBMIT_ERROR`, `GITHUB_ERROR`, `NETWORK_ERROR`, `NOT_FOUND`, `INVALID_ARGS`, `CANCELLED`

Exit codes: `0` success, `1` error, `2` cancelled

## How It Was Built

The implementation used a parallel team of 3 agents, each working in an isolated git worktree:

| Agent | Scope | Files Created |
|-------|-------|---------------|
| **reader** | Leaderboard pipeline | `leaderboard-client.ts`, `leaderboard.ts` |
| **runner** | Eval execution pipeline | `eval-runner.ts`, `run.ts` |
| **submitter** | Submit pipeline | `parquet-builder.ts`, `github-client.ts`, `submit-service.ts`, `submit.ts` |

Pre-existing files (from Phase 1): `index.ts`, `types/index.ts`, `utils/errors.ts`, `utils/output.ts`, `benchmark-registry.ts`, `config-manager.ts`, `eval-log-reader.ts`, `job-manager.ts`, `benchmarks.ts`, `status.ts`, `results.ts`

### Bug Found During Integration

The CSV parser used naive `split(",")` which broke on quoted score values like `"[0.852, 0.0112]"` — the comma inside the brackets was treated as a field separator. Fixed by adding a proper `splitCsvLine()` function that respects double-quoted fields.

## Porting Decisions

| Decision | Python (original) | TypeScript (new) | Why |
|----------|-------------------|------------------|-----|
| Eval execution | Worker subprocess, config via stdin JSON | Direct `inspect eval` CLI via `Bun.spawn` | Simpler, no intermediate worker needed |
| HuggingFace data | `hf_hub_download()` Python SDK | Direct `fetch()` to resolve URL | Eliminates Python dependency |
| Parquet writing | PyArrow (`pa.schema`, `pq.write_table`) | `@dsnp/parquetjs` (`ParquetWriter.openFile`) | Only npm package needed |
| GitHub API | `httpx.Client` with base URL | `fetch()` with manual URL construction | Zero dependencies |
| CSV parsing | Python `csv.DictReader` | Hand-rolled (~30 LOC) with quote handling | Avoids npm dependency |
| .env parsing | Python custom parser | Hand-rolled (~60 LOC) | Matches Python behavior exactly |
| CLI parsing | N/A (was TUI) | Hand-rolled (~25 LOC) | Only 6 commands with simple flags |

## Interactive TUI Mode (Phase 2 — In Progress)

### What It Is

Running `satellite` with no arguments launches an **AI-assisted terminal UI** — "Claude Code for evaluations." Users converse with Claude in natural language; Claude uses evaluation tools (run benchmarks, view leaderboard, submit results) to accomplish tasks. The goal: type `make satellite` and an agent takes over.

**Stack**: Bun + React 19 + Ink 6 + @inkjs/ui + Anthropic SDK
**Visual style**: Claude Code — streaming text, bordered tool panels, braille spinners, progress bars, status bar.

### Entry Point

In `cli/src/index.ts`, a 4-line gate before the existing switch/case:

```typescript
const isInteractive = !cli.command && process.stdout.isTTY && !cli.flags.json;
if (isInteractive) {
  const { startUI } = await import("./ui/main.js");
  return startUI();
}
```

Existing CLI commands (`satellite benchmarks`, `satellite run`, etc.) remain 100% unchanged.

### New File Structure (17 files, ~870 lines)

```
cli/src/ui/
├── main.tsx                    # Ink render() entry point
├── app.tsx                     # Root component, wires hooks to components
├── theme.ts                    # Colors, borders, spinner frames, tool verbs, pricing
├── types.ts                    # DisplayMessage, ToolCallDisplay, ConversationState
├── hooks/
│   ├── use-conversation.ts     # Core: Claude API streaming + tool execution loop (262 lines)
│   └── use-token-tracker.ts    # Token/cost accumulation
├── components/
│   ├── message-history.tsx     # <Static> wrapper for finalized messages
│   ├── user-message.tsx        # "> text" in green
│   ├── assistant-message.tsx   # "● text" in yellow + blinking cursor while streaming
│   ├── tool-call-panel.tsx     # Bordered panel: spinner/progress/result + status
│   ├── progress-bar.tsx        # ████░░░░ 42/100 (42%)
│   ├── spinner.tsx             # Braille frames: ⣾⣽⣻⢿⡿⣟⣯⣷
│   ├── input-bar.tsx           # Text input at bottom with "> " prompt
│   └── status-bar.tsx          # claude-sonnet-4-5 │ ↑1.2k ↓0.5k │ $0.004
└── tools/
    ├── schemas.ts              # TOOL_SCHEMAS array for Claude API
    ├── executor.ts             # Routes tool calls to existing service functions
    └── formatters.ts           # Tool result → human-readable display text
```

### Core Data Flow

```
User types message → sendMessage(text)
  │
  ▼
apiMessages.push({ role: "user", content: text })     ← useRef, never triggers re-render
  │
  ▼
client.messages.stream({ model, messages, tools })
  │
  ├─ "text" event → append to streamingText useState → <AssistantMessage> re-renders
  ├─ "contentBlock" (tool_use) → add to activeToolCalls[] → <ToolCallPanel> appears
  │
  ▼
stop_reason === "tool_use"?
  YES → executeTool(name, params, onProgress) → update ToolCallDisplay status/progress
      → push tool_result to apiMessages → LOOP (call stream again)
  NO  → finalize: move streamingText + activeToolCalls → finalizedMessages (<Static>)
```

### What's Done (Phase 1 MVP)

| Component | Status | Notes |
|-----------|--------|-------|
| Chat input with streaming response | ✅ | Token-by-token via Anthropic SDK stream events |
| Tool call visualization | ✅ | Bordered panels with running/completed/error states |
| `list_benchmarks` tool | ✅ | Returns all 7 benchmarks |
| `run_eval` tool with progress bar | ✅ | Live progress via fs.watch + polling |
| Status bar (model, tokens, cost) | ✅ | Sonnet 4 pricing ($0.003/1k in, $0.015/1k out) |
| Braille spinners | ✅ | 80ms frame animation with contextual verb labels |
| Message history via `<Static>` | ✅ | Render-once for finalized messages |
| Entry point gate | ✅ | `!cli.command && isTTY && !json` |
| TypeScript compilation | ✅ | `bunx tsc --noEmit` passes clean |
| CLI regression | ✅ | All existing commands unchanged |

### What's Missing (Phase 2 — Full Agent)

#### Critical: Can't run without these

1. **`ANTHROPIC_API_KEY` in `.env`** — The Claude SDK reads from env. Current `.env` has OpenRouter/GitHub/HF keys but no Anthropic key. Without it, the TUI crashes on first message.

2. **Makefile target** — Need `make satellite` in root Makefile:
   ```makefile
   .PHONY: satellite
   satellite:
   	cd cli && bun install --frozen-lockfile && bun run src/index.ts
   ```

3. **Bun setup in `make setup`** — Current setup is Python-only (uv). Need to install Bun and `cd cli && bun install` as part of project setup.

#### Missing Tools: Agent is limited to 2 of 8

The services exist and are tested. Only the UI tool schemas + executor wiring is needed.

| Tool | Service | Schema | Executor | What It Does |
|------|---------|--------|----------|-------------|
| `list_benchmarks` | `benchmark-registry.ts` | ✅ | ✅ | List available benchmarks |
| `run_eval` | `eval-runner.ts` | ✅ | ✅ | Run a benchmark with progress |
| `list_jobs` | `job-manager.ts:listJobs()` | ❌ | ❌ | See past evaluation runs |
| `get_job_results` | `job-manager.ts:getJobResults()` | ❌ | ❌ | Read scores from a completed job |
| `check_job_status` | `job-manager.ts:loadJob()` | ❌ | ❌ | Poll a running job's status |
| `fetch_leaderboard` | `leaderboard-client.ts:fetchLeaderboard()` | ❌ | ❌ | View current rankings |
| `get_eval_settings` | `config-manager.ts:loadEvalSettings()` | ❌ | ❌ | Read eval configuration |
| `submit_to_leaderboard` | `submit-service.ts:submitToLeaderboard()` | ❌ | ❌ | Submit via GitHub PR |

#### Agent Autonomy Gaps

| Gap | Impact | Fix |
|-----|--------|-----|
| No `--prompt` flag or stdin mode | Can't pipe initial instructions (`echo "run teleqna" \| satellite`) | Add `--prompt` flag to skip interactive input |
| No Ctrl+C graceful shutdown | May leave orphan `inspect eval` processes | Wire useInput Ctrl+C to cancel streaming + kill subprocess |
| Model hardcoded to `claude-sonnet-4-20250514` | Can't use cheaper/faster models | Read from `SATELLITE_AI_MODEL` env or `--model` flag |
| No session persistence | Agent loses context between runs | Save/load `~/.satellite/sessions/` |

### Dependencies Added for TUI

```json
{
  "@anthropic-ai/sdk": "^0.78.0",
  "ink": "^6.8.0",
  "react": "^19.2.4",
  "@inkjs/ui": "^2.0.0",
  "@types/react": "^19.2.14"
}
```

Also: `"jsx": "react-jsx"` added to `tsconfig.json` and `"src/**/*.tsx"` to include.

---

## What's Next

### Tests (Phase 5)

```bash
# Unit tests for services
bun test tests/services/

# Command integration tests with fixtures
bun test tests/commands/

# Full test suite
bun test
```

Test fixtures needed:
- Sample Inspect AI JSON log files (success, error, started, cancelled)
- Sample CSV leaderboard data
- Sample job manifests

### Compiled Binary

```bash
cd cli
bun build src/index.ts --compile --outfile satellite
./satellite benchmarks | jq .
```

### End-to-End Verification

```bash
# 1. List benchmarks
./satellite benchmarks

# 2. Run a quick eval
./satellite run --benchmark teleqna --model openai/gpt-4o --limit 5

# 3. Check status
./satellite status

# 4. View results
./satellite results --job job_YYYYMMDD_HHMMSS

# 5. Fetch leaderboard
./satellite leaderboard

# 6. Submit (against test repo first)
./satellite submit --job job_YYYYMMDD_HHMMSS --model openai/gpt-4o --token ghp_...
```

## Dependencies

**Runtime** (5 packages):
- `@dsnp/parquetjs` ^1.8.0 — Parquet file writing
- `@anthropic-ai/sdk` ^0.78.0 — Claude API (interactive TUI)
- `ink` ^6.8.0 — React for CLI (interactive TUI)
- `react` ^19.2.4 — React runtime (interactive TUI)
- `@inkjs/ui` ^2.0.0 — Ink UI components (interactive TUI)

**Dev** (3 packages):
- `typescript` ^5.7.0
- `@types/bun` — Bun runtime types
- `@types/react` ^19.2.14 — React type definitions

**External** (not managed by npm):
- `inspect` CLI — Python-based eval runner (invoked as subprocess)
- `bun` >= 1.0 — JavaScript runtime
