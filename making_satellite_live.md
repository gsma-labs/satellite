# Making Satellite Live

How we took a Python TUI app and made it accessible from any browser via a shareable URL.

---

## The Goal

For a presentation, we need Satellite accessible via a clean URL (e.g., `satellite-demo.fly.dev`). The audience watches while you drive the TUI from the browser. When you click "Check Traces" in the TUI, the Inspect AI dashboard opens in a new browser tab.

## Architecture

```
Browser                        Container
──────                         ─────────
https://satellite-demo.fly.dev ──→ nginx:8080 ──→ ttyd:7681 ──→ uv run satellite
                                                                    │
https://satellite-demo.fly.dev:7575 ──→ inspect view:7575  ◄───────┘
                                                         (auto-started by Satellite)
```

- **nginx** reverse-proxies HTTP + WebSocket to ttyd
- **ttyd** provides a browser-based terminal that runs `uv run satellite`
- **Satellite** launches `inspect view` on port 7575 for trace viewing
- **supervisord** manages nginx + ttyd as child processes

---

## What We Changed

### 1. Made inspect view host configurable (`app.py`)

Previously, inspect view always bound to `127.0.0.1` — unreachable from outside the container. Added an env var to control it:

```python
# src/satellite/app.py (line 24)
INSPECT_VIEW_HOST = os.environ.get("SATELLITE_VIEW_HOST", "127.0.0.1")
```

And passed `--host` to the inspect view command:

```python
cmd = [
    *INSPECT_VIEW_CMD,
    "--log-dir", str(log_dir),
    "--port", str(INSPECT_VIEW_PORT),
    "--host", INSPECT_VIEW_HOST,       # ← new
]
```

**Why:** In production, set `SATELLITE_VIEW_HOST=0.0.0.0` so the trace viewer is reachable on port 7575 from outside. Locally, the default `127.0.0.1` keeps it private.

### 2. Made trace viewer URLs configurable (`job_detail_modal.py`, `main.py`)

The "Check Traces" link and "Logs" link were hardcoded to `http://127.0.0.1:7575`. That URL is meaningless to someone viewing the TUI remotely. Made both configurable:

```python
# src/satellite/modals/scripts/job_detail_modal.py (line 20-22)
INSPECT_TRACES_BASE_URL = os.environ.get(
    "SATELLITE_TRACES_URL", "http://127.0.0.1:7575/#/logs"
)
```

```python
# src/satellite/screens/main.py (line 173)
url = os.environ.get("SATELLITE_TRACES_URL", "http://localhost:7575")
```

**Why:** In production, set `SATELLITE_TRACES_URL=https://satellite-demo.fly.dev:7575/#/logs` so trace links point to the public URL.

### 3. Added headless browser fallback

When running inside ttyd (no display server), `webbrowser.open()` fails. Both call sites now catch the exception and show a clickable URL notification instead:

```python
try:
    webbrowser.open(url)
except Exception:
    self.app.notify(f"Open: {url}")
```

**Why:** In ttyd's xterm.js terminal, URLs in notifications are auto-detected and clickable (Ctrl+Click). So the user still gets a working link.

### 4. Created `.dockerignore`

```
.venv/
.git/
.github/
.claude/
__pycache__/
*.pyc
.env
logs/
```

**Why:** Without this, `COPY . /app` sends the entire `.venv/` (hundreds of MB) and `.git/` history to the Docker daemon. The `.dockerignore` cuts the build context from ~700MB to ~100KB.

---

## Deployment Files

All in `deploy/`:

### `Dockerfile`

```dockerfile
FROM python:3.13-slim

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx supervisor git curl && \
    rm -rf /var/lib/apt/lists/*

# ttyd from GitHub releases (not in Debian repos)
ARG TTYD_VERSION=1.7.7
RUN ARCH=$(uname -m) && \
    curl -Lo /usr/local/bin/ttyd \
      "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.${ARCH}" && \
    chmod +x /usr/local/bin/ttyd

# uv (Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Layer caching: install deps first, then copy source
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project

COPY . .
RUN uv sync --no-dev

# Deployment configs
COPY deploy/nginx.conf /etc/nginx/sites-available/default
COPY deploy/supervisord.conf /etc/supervisor/conf.d/satellite.conf

EXPOSE 8080 7575
CMD ["supervisord", "-n"]
```

**Key decisions:**
- **ttyd from GitHub releases** — not available in Debian Trixie's apt repos
- **Two-stage `uv sync`** — deps are cached in a Docker layer; code-only changes skip the ~2.5 min dependency install
- **`--no-dev`** — production image doesn't need pytest, etc.

### `nginx.conf`

```nginx
server {
    listen 8080;
    location / {
        proxy_pass http://127.0.0.1:7681;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

**Why nginx at all?** ttyd speaks WebSocket, but Fly.io's edge proxy expects standard HTTP on the internal port. nginx handles the HTTP→WebSocket upgrade cleanly. The 86400s read timeout keeps the WebSocket alive for 24 hours.

### `supervisord.conf`

```ini
[supervisord]
nodaemon=true

[program:ttyd]
command=ttyd -W -p 7681 uv run satellite
directory=/app
environment=TERM="xterm-256color"
autostart=true
autorestart=true

[program:nginx]
command=nginx -g "daemon off;"
autostart=true
autorestart=true
```

**Key decisions:**
- **`-W` flag** on ttyd enables writable mode (keyboard input works)
- **`TERM=xterm-256color`** ensures the TUI renders colors correctly
- **`autorestart=true`** — if satellite crashes, ttyd restarts it on next browser connect
- **Environment variables** from Docker/Fly.io (`SATELLITE_VIEW_HOST`, etc.) propagate through supervisord to child processes automatically

### `fly.toml`

```toml
app = "satellite-demo"
primary_region = "lhr"  # London

[build]
  dockerfile = "deploy/Dockerfile"

[env]
  SATELLITE_VIEW_HOST = "0.0.0.0"
  SATELLITE_TRACES_URL = "https://satellite-demo.fly.dev:7575/#/logs"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

[[services]]
  internal_port = 7575
  protocol = "tcp"
  [[services.ports]]
    port = 7575
    handlers = ["tls", "http"]

[[vm]]
  memory = "65536mb"
  cpu_kind = "performance"
  cpus = 8
```

**Key decisions:**
- **`auto_stop_machines = false`** — for a demo, the machine should always be warm
- **Two services** — port 8080 (main TUI) and port 7575 (trace viewer)
- **Port 7575 requires dedicated IPv4** — Fly.io's shared IPv4 only routes port 443/80. Run `fly ips allocate-v4` (~$2/mo) to expose 7575.
- **64GB RAM / 8 performance CPUs** — overkill for the TUI itself (~100MB RSS), but eliminates any risk of OOM during live demos. Fly.io bills by the second, so a few hours costs ~$2-5. Destroy the machine after the demo to stop billing.

---

## Environment Variables

| Variable | Default | Production Value | Purpose |
|----------|---------|-----------------|---------|
| `SATELLITE_VIEW_HOST` | `127.0.0.1` | `0.0.0.0` | Bind address for inspect view |
| `SATELLITE_TRACES_URL` | `http://127.0.0.1:7575/#/logs` | `https://satellite-demo.fly.dev:7575/#/logs` | Public URL for trace links |
| `SATELLITE_JOBS_DIR` | Auto-detected | `/app/src/satellite/jobs` | Override jobs directory path |
| `OPENAI_API_KEY` | — | Set via `fly secrets` | LLM API key |
| `HF_TOKEN` | — | Set via `fly secrets` | HuggingFace token |

---

## Running Locally

```bash
# Build
docker build -f deploy/Dockerfile -t satellite-demo .

# Run
docker run -p 8080:8080 -p 7575:7575 \
  -e SATELLITE_VIEW_HOST=0.0.0.0 \
  -e SATELLITE_TRACES_URL="http://localhost:7575/#/logs" \
  satellite-demo

# Open http://localhost:8080 in your browser
```

### Browser Cache Gotcha

If you previously ran a different web app on `localhost:8080` (e.g., an "Eval Runner" with a Service Worker), the browser will serve the OLD app from cache even though the server is returning ttyd HTML.

**Fix:**
1. Open DevTools → Application → Storage → **Clear site data**
2. Application → Service Workers → **Unregister** any listed workers
3. Hard refresh: `Cmd+Shift+R`
4. Or just use an **incognito window**

You can verify the server is correct with: `curl -s http://localhost:8080 | grep '<title>'` → should show `ttyd - Terminal`.

---

## Deploying to Fly.io

```bash
# One-time setup
fly auth login
fly apps create satellite-demo
fly secrets set OPENAI_API_KEY=sk-... HF_TOKEN=hf_...

# Deploy
fly deploy --config deploy/fly.toml

# Allocate dedicated IPv4 for port 7575
fly ips allocate-v4

# Access
# https://satellite-demo.fly.dev       → Satellite TUI
# https://satellite-demo.fly.dev:7575  → Inspect AI traces
```

---

## Files Changed

| File | Action | Lines Changed |
|------|--------|---------------|
| `src/satellite/app.py` | Modified | +3 (env var + --host flag) |
| `src/satellite/modals/scripts/job_detail_modal.py` | Modified | +6 (configurable URL + fallback) |
| `src/satellite/screens/main.py` | Modified | +5 (configurable URL + fallback) |
| `.dockerignore` | Created | Excludes .venv, .git, etc. |
| `deploy/Dockerfile` | Created | Layer-cached Python build |
| `deploy/nginx.conf` | Created | WebSocket reverse proxy |
| `deploy/supervisord.conf` | Created | Process manager |
| `deploy/fly.toml` | Created | Fly.io deployment config |
| `deploy/README.md` | Created | Quick-start instructions |

---

## Fix: TUI Stuck on Package Installation Screen (2026-03-01)

After the initial deployment, visiting `https://satellite-demo.fly.dev` showed ttyd stuck on uv's package installation output instead of the TUI:

```
Built satellite @ file:///app
Uninstalled 1 package in 5ms
Installed 6 packages in 24ms
```

**Root cause:** The supervisord command `ttyd -W -p 7681 uv run satellite` triggers `uv run`, which re-syncs the virtual environment on every container start — even though `uv sync --no-dev` already ran during the Docker build. The git dependency (`evals @ git+https://github.com/gsma-labs/evals.git@main`) made this especially slow as uv tried to verify the remote repository.

**Fix:** Added `--no-sync` to skip runtime dependency resolution:

```diff
# deploy/supervisord.conf
- command=ttyd -W -p 7681 uv run satellite
+ command=ttyd -W -p 7681 uv run --no-sync satellite
```

This tells uv to trust the pre-built `.venv` from the Docker build and launch the app immediately. The TUI now renders without delay.

---

## Fix: OOM Kills on Fly.io (2026-03-01)

After fixing the package installation issue, the TUI still showed a blank page. Investigation with `fly logs` revealed the real problem: **the satellite process was being OOM-killed within ~60 seconds of startup**.

```
Out of memory: Killed process 667 (satellite) total-vm:550800kB, anon-rss:102356kB
Process appears to have been OOM killed!
```

**Root cause:** Fly.io created machines with only **256MB RAM** (`shared-cpu-1x` default). The satellite Python process alone uses ~100MB RSS. Combined with the Python runtime, nginx, ttyd, and supervisord overhead, the total memory demand exceeded 256MB. The OOM killer terminated the satellite process with exit code 137, causing a crash loop — the app never stayed alive long enough to render.

Additionally, Fly.io defaulted to **2 machines** — unnecessary for a demo.

### Fix 1: Add `[[vm]]` section to `fly.toml`

```toml
[[vm]]
  memory = "65536mb"
  cpu_kind = "performance"
  cpus = 8
```

This explicitly allocates 64GB RAM and 8 dedicated performance CPUs. For a demo that runs for a few hours, Fly.io bills by the second — roughly **$50-60 for 3 days** at this spec, or proportionally less for shorter use.

**Why so much?** The TUI itself only needs ~512MB comfortably, but for a live demo presentation we want zero risk of slowdowns or OOM kills. The cost for a few hours is trivial. After the demo, destroy the machine to stop billing.

### Fix 2: Scale down to 1 machine

```bash
fly scale count 1 --config fly.toml
```

A demo only needs one instance. This also halves the compute cost.

### Fix 3: Redeploy

```bash
fly deploy --config fly.toml
```

After redeploying, the logs confirmed both nginx and ttyd entered `RUNNING` state with **no OOM kills**. The nginx process spawned 8 worker processes (one per CPU).

---

## Automated Deployment Validation (2026-03-01)

Created `deploy/test_deployment.py` — a Playwright script that validates a live deployment is actually working (not showing a blank page).

### What it checks

1. **Page loads** — HTTP 200 from the deployment URL
2. **xterm.js terminal present** — `div.xterm` element exists (ttyd rendered)
3. **TUI content visible** — `.xterm-rows` contains meaningful text (not blank)
4. **Screenshot captured** — saved to `deploy/screenshots/deployment_validation.png`

### Usage

```bash
pip install playwright && playwright install chromium
python deploy/test_deployment.py --url https://satellite-demo.fly.dev
```

Returns exit code 0 on success, 1 on failure. Useful for CI or quick post-deploy sanity checks.

---

## Network Considerations for Live Demos

The TUI runs server-side; the browser is just a thin terminal client over WebSocket.

**What travels over the network:**
- Keystrokes (browser → server)
- Screen updates (server → browser, just text + ANSI codes)

**Latency matters:** The Fly.io machine is in `lhr` (London). Expect:
- From London: ~5-10ms — feels instant
- From US East: ~100-150ms — noticeable but usable
- From Asia/Australia: 200-300ms — sluggish

**Bandwidth:** Barely relevant. Terminal data is a few KB per screen update.

**Server-side API calls are unaffected:** Satellite polls GPU infrastructure APIs from the Fly.io machine. Your browser's internet speed doesn't impact that.

**For demos far from London**, redeploy to a closer region:

```bash
fly deploy --config fly.toml --region iad   # US East (Virginia)
fly deploy --config fly.toml --region sjc   # US West (San Jose)
fly deploy --config fly.toml --region sin   # Singapore
```

---

## Post-Demo Cleanup

After the demo, stop billing by destroying the machine:

```bash
# Destroy the running machine
fly machines list --config fly.toml          # get machine ID
fly machines destroy <machine-id> --config fly.toml --force

# Or destroy the entire app
fly apps destroy satellite-demo
```

To re-enable for another demo, just `fly deploy --config fly.toml` again.

---

## Fix: Check Traces Showed Wrong Job (2026-03-01)

Clicking "Check Traces" for a specific job in the TUI opened the Inspect AI viewer but showed incorrect logs — always the same job regardless of which one was clicked.

**Root cause:** `PACKAGE_ROOT` (`Path(__file__).parent`) resolves to different paths depending on install mode:

- **Editable install** (local dev via `uv run`): Points to `src/satellite/` in the source tree — correct
- **Non-editable install** (Docker via `uv sync`): Points to `.venv/lib/python3.13/site-packages/satellite/` — wrong

The `jobs/` directory lives in the source tree (`/app/src/satellite/jobs/`), but `inspect view --log-dir` was pointed at `.venv/.../satellite/jobs/` — an empty directory created at runtime. Only jobs run during the current container session appeared; all pre-existing jobs were invisible.

**Fix:** Made `DEFAULT_JOBS_DIR` resolve dynamically in `job_manager.py`:

1. Check `SATELLITE_JOBS_DIR` env var (explicit override)
2. Check `PACKAGE_ROOT / "jobs"` (works in editable installs)
3. Fall back to `src/satellite/jobs` relative to cwd (works in Docker where cwd is `/app`)

No changes needed to the Dockerfile or fly.toml — the fallback handles the Docker case automatically.
