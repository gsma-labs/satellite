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
    "message_limit": null
}

Exit codes: 0=success, 1=error, 2=cancelled
"""

import json
import sys
from importlib import import_module

from inspect_ai import Task

from satellite.services.evals.registry import BENCHMARKS_BY_ID

# JSON enables programmatic parsing for leaderboard aggregation
EVAL_LOG_FORMAT = "json"
# Disable rich terminal output; we're headless in a subprocess
EVAL_DISPLAY = "none"


def load_task(benchmark_id: str) -> Task | None:
    """Load a Task by importing its module."""
    config = BENCHMARKS_BY_ID.get(benchmark_id)
    if not config:
        return None
    module = import_module(config.module_path)
    return getattr(module, config.function_name)()


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

    tasks = [t for b in config["benchmarks"] if (t := load_task(b))]
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


if __name__ == "__main__":
    sys.exit(main())
