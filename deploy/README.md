# Hosting Satellite on Fly.io

Deploy Satellite as a remote TUI accessible via any browser.

## Architecture

- **Main URL** (`https://satellite-demo.fly.dev`) → nginx → ttyd → Satellite TUI
- **Traces URL** (`https://satellite-demo.fly.dev:7575`) → Inspect AI trace viewer

## Prerequisites

- [flyctl](https://fly.io/docs/flyctl/install/) installed
- Fly.io account

## Deploy

```bash
# Authenticate
fly auth login

# Create the app (first time only)
fly apps create satellite-demo

# Set secrets (API keys are never baked into the image)
fly secrets set OPENAI_API_KEY=sk-... HF_TOKEN=hf_...

# Deploy (from project root)
fly deploy --config deploy/fly.toml

# Allocate a dedicated IPv4 (required for port 7575)
fly ips allocate-v4
```

## Access

| URL | What |
|-----|------|
| `https://satellite-demo.fly.dev` | Satellite TUI in browser |
| `https://satellite-demo.fly.dev:7575` | Inspect AI trace viewer |

## Environment Variables

| Variable | Default | Server Value | Purpose |
|----------|---------|-------------|---------|
| `SATELLITE_VIEW_HOST` | `127.0.0.1` | `0.0.0.0` | Bind address for inspect view |
| `SATELLITE_TRACES_URL` | `http://127.0.0.1:7575/#/logs` | `https://satellite-demo.fly.dev:7575/#/logs` | Public URL for trace viewer |
| `OPENAI_API_KEY` | — | Set via `fly secrets` | LLM API key |
| `HF_TOKEN` | — | Set via `fly secrets` | HuggingFace token |

## Local Testing

```bash
# Build the container (from project root)
docker build -f deploy/Dockerfile -t satellite-demo .

# Run
docker run -p 8080:8080 -p 7575:7575 \
  -e SATELLITE_VIEW_HOST=0.0.0.0 \
  -e SATELLITE_TRACES_URL="http://localhost:7575/#/logs" \
  satellite-demo

# Open http://localhost:8080 in your browser
```
