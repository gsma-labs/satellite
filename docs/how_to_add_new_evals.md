# How to Add New Evaluations

This guide explains how new evaluations flow from the `otelcos/evals` repository into the satellite TUI.

## Architecture Overview

```
otelcos/evals                          satellite
┌─────────────────────┐               ┌─────────────────────────────┐
│ src/evals/          │               │ services/eval_registry.py   │
│   _registry.py      │──imports──────│   EVAL_METADATA             │
│   __all__ = [       │               │   get_available_evals()     │
│     "teleqna",      │               └──────────────┬──────────────┘
│     "new_eval",     │                              │
│   ]                 │                              ▼
└─────────────────────┘               ┌─────────────────────────────┐
                                      │ UI Components               │
                                      │   - Run Evals Modal         │
                                      │   - Leaderboard Modal       │
                                      └─────────────────────────────┘
```

## When a New Eval is Added to otelcos/evals

1. **Automatic**: The eval ID appears in `evals._registry.__all__`
2. **Manual**: You must add metadata to satellite's `EVAL_METADATA`

## Step-by-Step: Adding a New Eval

### Step 1: Update Dependencies

After otelcos/evals adds a new evaluation, update your dependencies:

```bash
cd satellite
uv sync --upgrade-package evals
```

### Step 2: Add Metadata to eval_registry.py

Open `src/satellite/services/eval_registry.py` and add an entry to `EVAL_METADATA`:

```python
EVAL_METADATA: dict[str, dict] = {
    # ... existing evals ...

    "new_eval_id": {
        "name": "New Eval Display Name",    # Full name shown in UI
        "short_name": "Short",              # Column header in leaderboard (max ~6 chars)
        "description": "What this evaluation tests",
        "hf_column": "column_in_huggingface",  # Column name in GSMA/leaderboard dataset
    },
}
```

### Step 3: Verify

Run satellite and check:

```bash
uv run python -m satellite
```

1. Press `2` (Evals) → The new eval should appear in the list
2. Press `3` (Preview Leaderboard) → The new column should appear (with `--` if no data yet)

## Field Reference

| Field | Description | Example |
|-------|-------------|---------|
| `name` | Full display name | `"TeleQnA"` |
| `short_name` | Leaderboard column header | `"QnA"` |
| `description` | Shown below the name in eval list | `"Question answering benchmark"` |
| `hf_column` | Column name in HuggingFace dataset | `"teleqna"` |

## Finding the HuggingFace Column Name

The leaderboard data comes from the `GSMA/leaderboard` dataset on HuggingFace. To find the correct column name:

1. Visit https://huggingface.co/datasets/GSMA/leaderboard
2. Look at the dataset columns
3. Match the new eval's column name

Common patterns:
- `teleqna` → `"teleqna"`
- `three_gpp` → `"3gpp_tsg"`

## What Happens Without Metadata

If an eval exists in the registry but lacks metadata in satellite:

1. A warning is logged: `No metadata for eval 'new_eval_id' - add to EVAL_METADATA`
2. The eval is **not shown** in the UI
3. The leaderboard won't display that column

## Example: Adding "TeleConfig" Eval

Suppose otelcos/evals adds a new `teleconfig` evaluation:

```python
# In src/satellite/services/eval_registry.py

EVAL_METADATA: dict[str, dict] = {
    "teleqna": { ... },
    "telelogs": { ... },
    "telemath": { ... },
    "teletables": { ... },
    "three_gpp": { ... },

    # New eval
    "teleconfig": {
        "name": "TeleConfig",
        "short_name": "Config",
        "description": "Network configuration understanding benchmark",
        "hf_column": "teleconfig",
    },
}
```

## Troubleshooting

### Eval not appearing in UI

1. Check the registry is updated:
   ```bash
   uv run python -c "from evals._registry import __all__; print(__all__)"
   ```
2. Check metadata exists in `EVAL_METADATA`
3. Check for typos in the eval ID

### Leaderboard shows "--" for all entries

The HuggingFace dataset may not have data for this eval yet. This is expected for new evals.

### Import errors after updating

Run a clean sync:
```bash
uv sync --reinstall-package evals
```
