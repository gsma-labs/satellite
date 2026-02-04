# Satetoad Makefile - uses uv for dependency management

# Load .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

run := uv run python -m satetoad

.PHONY: run
run:
	$(run)

.PHONY: install
install:
	uv sync

.PHONY: dev
dev:
	uv sync --dev

.PHONY: test-import
test-import:
	uv run python -c "from satetoad.app import SatetoadApp; print('Import OK')"

.PHONY: lint
lint:
	uv run ruff check src/

.PHONY: format
format:
	uv run ruff format src/

.PHONY: clean
clean:
	rm -rf .venv __pycache__ src/satetoad/__pycache__ .ruff_cache
