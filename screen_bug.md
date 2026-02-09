# Bug Fix: Mouse Escape Codes Leaking to Terminal

## Problem

When running `uv run satellite` from `/ot/satellite/`, mouse escape sequences (`^[[<35;15;3M...`) appeared at the top of the screen when moving the mouse. The same command worked correctly when run from `/ot/`.

## Root Cause

The `evals` package imports `inspect-ai` which has its own terminal handling that conflicts with Textual's SGR mouse tracking driver.

| Location | `evals` package | Behavior |
|----------|-----------------|----------|
| `/ot/.venv` | Not installed | Import fails → fallback metadata → works |
| `/ot/satellite/.venv` | Installed | Imports `inspect-ai` → terminal conflict → bug |

### Import Chain (the problem)

```
eval_registry.py
  → _get_registry_evals()
    → from evals._registry (imports inspect-ai)
      → inspect-ai initializes terminal handling (403 modules loaded!)
        → Conflicts with Textual's mouse driver
          → Mouse events leak to stdout as raw escape codes
```

## Failed Attempt: Timer-based Preload

The first fix attempted to use a 0.5s timer to delay the import:

```python
# This DID NOT WORK
def on_mount(self) -> None:
    self.set_timer(0.5, self._preload_evals)  # Still causes escape codes!
```

**Why it failed**: 0.5 seconds is an arbitrary guess that doesn't guarantee Textual has full terminal control. The import still happened before Textual's driver was ready.

## Working Solution: Import BEFORE Textual Starts

The problem is that inspect-ai's terminal handling conflicts with Textual's driver **whenever it's imported while Textual is running** - not just at startup.

The fix: import evals/inspect-ai **before** `app.run()` is called. At that point, the terminal is still "normal", so inspect-ai initializes without conflict. Then Textual takes over cleanly.

### File: `src/satellite/app.py`

Import in `main()` before Textual starts:

```python
def main() -> None:
    """Entry point for the application."""
    # Import evals/inspect-ai BEFORE Textual takes terminal control.
    # inspect-ai has terminal handling that conflicts with Textual's driver.
    # By importing here (before app.run()), inspect-ai initializes on a
    # normal terminal, then Textual takes over cleanly.
    try:
        # Import all evals (triggers full inspect-ai initialization)
        from evals._registry import (  # noqa: F401
            telelogs,
            telemath,
            teleqna,
            teletables,
            three_gpp,
        )
    except ImportError:
        pass  # evals not installed, will use fallback metadata

    app = SatelliteApp()
    app.run()
```

### File: `src/satellite/services/eval_registry.py`

Keep the dynamic import (needed for future evals) - it's now a no-op since module is already loaded:

```python
def _get_registry_evals() -> list[str]:
    """Get eval IDs from otelcos/evals registry."""
    try:
        from evals._registry import __all__ as registry_evals
        return list(registry_evals)  # Already imported, instant
    except ImportError:
        return list(EVAL_METADATA.keys())
```

## Benefits of This Fix

- **No terminal conflicts** - inspect-ai initializes before Textual exists
- **Dynamic loading preserved** - new evals in the registry are picked up automatically
- **inspect-ai available** - for running evaluations when needed
- **Modals work** - `get_benchmarks()` calls are instant (module already loaded)
- **No timing hacks** - deterministic import order, not arbitrary delays

## Key Insight

The conflict happens when inspect-ai initializes its terminal handling while Textual is already managing the terminal. The solution is sequencing: let inspect-ai initialize first (normal terminal), then let Textual take over.
