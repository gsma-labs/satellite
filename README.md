<img src="docs/demo.gif" alt="Satellite demo" width="600">

📡 wraps [Inspect AI](https://inspect.aisi.org.uk/) in a terminal interface
that lets you run the telecom benchmarks from [gsma-labs/evals](https://github.com/gsma-labs/evals),
track progress in real time, and submit results to the
[community leaderboard](https://github.com/gsma-labs/leaderboard) —
all without leaving your terminal.

> [!NOTE]
> **This is a beta.** It will be full of bugs — you've been warned.
>
> The whole purpose of this TUI is to:
> 1. **Make it easier to get into evals** — specially for people coming from telecommunications who are getting into LLM evaluations for the first time
> 2. **Give you a place to submit to the leaderboard easily** — run the benchmarks, see your scores, submit with a few keystrokes
>
> If you want to experiment hardcore, use a bunch of different parameters, or run evaluations at super scale on workstations or clusters — this might NOT be the best version for you. Stick to [gsma-labs/evals](https://github.com/gsma-labs/evals) and hack your way through [Inspect AI](https://inspect.aisi.org.uk/) directly.

## Quick Start

### 1. Install uv

Satellite uses [uv](https://docs.astral.sh/uv/getting-started/installation/) as its package manager. Install it first:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and setup

```bash
git clone https://github.com/gsma-labs/satellite.git
cd satellite
make setup
```

`make setup` installs Python 3.13, all dependencies, and registers the `satellite` command.

> **Linux note:** `make setup` may use `sudo` to install system libraries (libcairo2-dev).
> Running `sudo make setup` is supported: Python dependencies are installed as the invoking user (`$SUDO_USER`), not in `/root`.
> Running `make setup` directly as root (without `SUDO_USER`) is not supported.
> If you prefer to install system deps separately:
> ```bash
> sudo apt-get install -y libcairo2-dev pkg-config
> make setup
> ```

### 3. Run

```bash
uv run satellite
```

## What You Can Do

### Run Evaluations

Run any combination of the telecom benchmarks against your chosen model.
Satellite discovers available benchmarks from `evals._registry` automatically.

| Benchmark | Required Samples |
|-----------|-----------------|
| TeleQnA   | 1000            |
| TeleLogs  | 100             |
| TeleMath  | 100             |
| TeleTables| 100             |
| 3GPP      | 100             |
| ORANBench | 150             |
| srsRANBench | 150           |

Track running jobs with live progress bars, cancel jobs in progress, and inspect detailed scores and token usage per job. The Settings tab lets you configure sample limits, epochs, max connections, and token limits.

Evaluation tasks are defined in [gsma-labs/evals](https://github.com/gsma-labs/evals). Traces are viewable through the integrated [Inspect AI](https://inspect.aisi.org.uk/) viewer.

### Preview Leaderboard

View the current leaderboard rankings directly in the TUI. Your local results appear alongside remote entries so you can compare before submitting.

### Submit to Leaderboard

Submit your evaluation results to [gsma-labs/leaderboard](https://github.com/gsma-labs/leaderboard) as a pull request — all from within the TUI.

## Supported Models

Satellite supports all [Inspect-compatible model providers](https://inspect.aisi.org.uk/models.html) — including OpenAI, Anthropic, Google, Mistral, and more. Configure your model and API keys through the TUI.

## Submission Setup

To submit results, you need a GitHub token with the following permissions scoped to `gsma-labs/leaderboard`:

- `contents:read` and `contents:write`
- `pull_requests:write`

All currently registered benchmarks must be completed with the required sample counts before submission is allowed.

## Development

| Command        | Description              |
|----------------|--------------------------|
| `make deps`    | Install system libraries |
| `make setup`   | Install dependencies     |
| `make test`    | Run tests                |
| `make lint`    | Lint with Ruff           |
| `make format`  | Auto-format with Ruff    |
| `make run`     | Launch the TUI           |

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development guide.

## Documentation

- [Adding Evaluations](docs/how_to_add_new_evals.md) — how to register new benchmarks
- [Contributing](CONTRIBUTING.md) — development setup and code style

## Acknowledgments

Satellite's layout and TUI architecture were heavily inspired by
[Toad](https://github.com/batrachianai/toad), a beautiful Textual-based
terminal interface for AI coding agents. Huge kudos to the Toad team —
their work showed us how good a terminal UI can feel, and gave us
a strong foundation to build on.

## License

[AGPL-3.0](LICENSE)
