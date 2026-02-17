# Satellite Makefile - uses uv for dependency management

# Load .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

run := uv run satellite

.PHONY: run
run:
	$(run)

.PHONY: deps
deps:
	@if [ "$$(uname)" = "Linux" ] && ! pkg-config --exists cairo 2>/dev/null; then \
		echo "Installing system dependencies (libcairo2-dev)..."; \
		sudo apt-get update -qq && sudo apt-get install -y -qq libcairo2-dev pkg-config; \
	fi

.PHONY: setup
setup: deps
	@if [ "$$(id -u)" = "0" ] && [ -n "$${SUDO_USER:-}" ]; then \
		echo "Running Python setup as $$SUDO_USER..."; \
		sudo -u "$$SUDO_USER" -H sh -lc 'command -v uv >/dev/null 2>&1 || { echo "Installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }; UV_BIN="$$HOME/.local/bin/uv"; if [ -x "$$UV_BIN" ]; then "$$UV_BIN" sync --dev; else uv sync --dev; fi'; \
	elif [ "$$(id -u)" = "0" ]; then \
		echo "Error: running 'make setup' directly as root is not supported."; \
		echo "Run 'make setup' as a normal user (or via sudo from that user account)."; \
		exit 1; \
	else \
		command -v uv >/dev/null 2>&1 || { echo "Installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }; \
		UV_BIN="$$HOME/.local/bin/uv"; \
		if [ -x "$$UV_BIN" ]; then \
			"$$UV_BIN" sync --dev; \
		else \
			uv sync --dev; \
		fi; \
	fi

.PHONY: test
test:
	uv run pytest tests/ -v

.PHONY: check
check:
	@uv run python -c "from satellite.app import SatelliteApp; print('satellite ........... OK')"
	@uv run python -c "import inspect_ai; print('inspect-ai ......... OK')"
	@uv run python -c "import evals; print('evals .............. OK')"

.PHONY: lint
lint:
	uv run ruff check src/

.PHONY: format
format:
	uv run ruff format src/

.PHONY: clean
clean:
	rm -rf .venv __pycache__ src/satellite/__pycache__ .ruff_cache
