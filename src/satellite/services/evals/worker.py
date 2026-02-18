"""Subprocess entry point for running evals with clean file descriptors.

Textual's multiprocessing causes ValueError: bad value(s) in fds_to_keep.
The subprocess architecture provides isolation with a clean file descriptor table.

Reads JSON config from stdin:
{
    "model": "openai/gpt-4",
    "benchmarks": ["teleqna"],
    "log_dir": "/path",
    "limit": null,
    "epochs": 1,
    "max_connections": 10,
    "token_limit": null,
    "message_limit": null,
    "full_benchmark": false
}

If ``full_benchmark`` is omitted, it defaults to ``false`` (sample split).

Exit codes: 0=success, 1=error, 2=cancelled
"""

import inspect
import json
import logging
import sys
from collections.abc import Callable
from importlib import import_module

from inspect_ai import Task

from satellite.services.evals.registry import BENCHMARKS_BY_ID

_log = logging.getLogger(__name__)

# JSON enables programmatic parsing for leaderboard aggregation
EVAL_LOG_FORMAT = "json"
# Disable rich terminal output; we're headless in a subprocess
EVAL_DISPLAY = "none"


def _accepts_full_keyword(task_fn: Callable[..., object]) -> bool:
    """Return ``True`` when ``task_fn`` can be called with ``full=True``.

    Task factories should expose explicit keyword parameters (for example
    ``def teleqna(*, full: bool = False) -> Task``) so this inspection remains
    predictable.
    """
    try:
        signature = inspect.signature(task_fn)
    except (TypeError, ValueError) as exc:
        _log.debug("Could not inspect signature for task factory %r: %s", task_fn, exc)
        return False

    full_param = signature.parameters.get("full")
    if full_param is not None and full_param.kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    ):
        return True
    return any(
        param.kind is inspect.Parameter.VAR_KEYWORD
        for param in signature.parameters.values()
    )


def _ensure_task(result: object, benchmark_id: str, function_name: str) -> Task:
    """Validate task factory output and return it as ``Task``."""
    if isinstance(result, Task):
        return result
    raise TypeError(
        f"Task factory '{function_name}' for benchmark '{benchmark_id}' returned "
        f"{type(result).__name__}; expected inspect_ai.Task"
    )


def load_task(benchmark_id: str, full: bool = False) -> Task | None:
    """Load a Task by importing its module.

    Args:
        benchmark_id: The benchmark identifier (e.g. "teleqna").
        full: When ``True``, pass ``full=True`` to the task constructor so it
            uses the full dataset (``GSMA/ot-full-benchmarks``).

    Returns:
        An ``inspect_ai.Task`` when the benchmark factory exists. Task factories
        are expected to return ``Task`` instances.
    """
    config = BENCHMARKS_BY_ID.get(benchmark_id)
    if not config:
        return None
    module = import_module(config.module_path)
    task_fn = getattr(module, config.function_name, None)
    if not callable(task_fn):
        return None
    if full and _accepts_full_keyword(task_fn):
        return _ensure_task(task_fn(full=True), benchmark_id, config.function_name)
    return _ensure_task(task_fn(), benchmark_id, config.function_name)


def mark_started_logs_cancelled(log_dir: str) -> None:
    """Mark any 'started' logs in directory as 'cancelled'."""
    from inspect_ai.log import list_eval_logs, read_eval_log, write_eval_log

    for log_info in list_eval_logs(log_dir):
        log = read_eval_log(log_info)
        if log.status == "started":
            log.status = "cancelled"
            write_eval_log(log)


def run_evals(config: dict) -> int:
    """Execute eval_set and return exit code."""
    from inspect_ai import eval_set

    # Register Inspect hooks that write per-sample progress sidecar files.
    # This keeps the Satellite UI responsive without parsing large JSON logs repeatedly.
    import satellite.services.evals.inspect_progress_hook  # noqa: F401

    full = config.get("full_benchmark", False)
    tasks = [t for b in config["benchmarks"] if (t := load_task(b, full=full))]
    if not tasks:
        print(f"No valid tasks for benchmarks: {config['benchmarks']}", file=sys.stderr)
        return 1

    kwargs: dict = {
        "tasks": tasks,
        "model": config["model"],
        "log_dir": config["log_dir"],
        "epochs": config["epochs"],
        "max_connections": config["max_connections"],
        "log_format": EVAL_LOG_FORMAT,
        "display": EVAL_DISPLAY,
        # Keep Inspect logs detailed and viewable while the run is active.
        "log_samples": True,
        "log_realtime": True,
    }
    if "limit" in config:
        kwargs["limit"] = config["limit"]
    if "token_limit" in config:
        kwargs["token_limit"] = config["token_limit"]
    if "message_limit" in config:
        kwargs["message_limit"] = config["message_limit"]

    success, _ = eval_set(**kwargs)
    return 0 if success else 1


def main() -> int:
    """Run eval_set for a single model. Reads JSON config from stdin."""
    config: dict = {}
    try:
        config = json.load(sys.stdin)
        return run_evals(config)
    except KeyboardInterrupt:
        mark_started_logs_cancelled(config.get("log_dir", ""))
        print("Cancelled", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
