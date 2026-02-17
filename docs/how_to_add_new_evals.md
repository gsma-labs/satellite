# How New Evals Flow Into Satellite

Satellite now auto-discovers evaluations from `evals._registry.__all__`.

## What Is Automatic

When a new task is added in `gsma-labs/evals/src/evals/_registry.py`, Satellite will automatically:

1. Show it in **Run Evals**.
2. Load it in the eval worker.
3. Add it to leaderboard/submit layouts.
4. Include it in eligibility checks.

No per-eval hardcoding is needed in Satellite for normal additions.

## Required Step After Evals Changes

Satellite still needs an updated `evals` dependency:

```bash
cd satellite
uv lock --upgrade-package evals
uv sync --dev
```

## Quick Verification

```bash
uv run python -c "import evals._registry as r; print(r.__all__)"
uv run pytest tests/services/test_submit_eligibility.py tests/services/test_parquet_builder.py -q
```

Then run the UI:

```bash
uv run satellite
```

## Metadata Behavior

Satellite derives benchmark metadata from each task module with safe fallbacks:

1. `hf_column`: from `DEFAULT_DATASET_NAME` when available, else eval id.
2. Name/short name/description: known overrides for core benchmarks, generated fallback for new ones.
3. Required sample count: known overrides for official leaderboard benchmarks; best-effort inference for unknown tasks.

## Recommended Automation Workflow

To keep Satellite synced with frequent eval additions:

1. Add a scheduled GitHub Action that runs `uv lock --upgrade-package evals`.
2. Run CI tests on that branch.
3. Auto-open a PR with lockfile updates when changes are detected.

This keeps dependency updates reproducible while eliminating manual registry/layout edits.
