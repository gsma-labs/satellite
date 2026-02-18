"""Benchmark registry.

Satellite discovers benchmark tasks from ``evals._registry.__all__`` so newly
added evaluations in ``gsma-labs/evals`` appear in the UI automatically.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from importlib import import_module
from types import ModuleType
from typing import Callable

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    """Configuration for a single benchmark evaluation."""

    id: str
    name: str
    short_name: str
    description: str
    hf_column: str
    module_path: str
    function_name: str
    total_samples: int


_NAME_OVERRIDES: dict[str, str] = {
    "teleqna": "TeleQnA",
    "telelogs": "TeleLogs",
    "telemath": "TeleMath",
    "teletables": "TeleTables",
    "three_gpp": "3GPP",
    "oranbench": "ORANBench",
    "srsranbench": "srsRANBench",
}

_SHORT_NAME_OVERRIDES: dict[str, str] = {
    "teleqna": "QnA",
    "telelogs": "Logs",
    "telemath": "Math",
    "teletables": "Tables",
    "three_gpp": "3GPP",
    "oranbench": "ORAN",
    "srsranbench": "srsRAN",
}

_DESCRIPTION_OVERRIDES: dict[str, str] = {
    "teleqna": "Question answering benchmark for telecom domain",
    "telelogs": "Log analysis and troubleshooting benchmark",
    "telemath": "Mathematical reasoning for telecom calculations",
    "teletables": "Table understanding and extraction benchmark",
    "three_gpp": "3GPP specification understanding benchmark",
    "oranbench": "O-RAN specification understanding benchmark",
    "srsranbench": "srsRAN codebase understanding benchmark",
}

# Required sample counts for leaderboard eligibility (small benchmark split).
_SAMPLE_COUNT_OVERRIDES: dict[str, int] = {
    "teleqna": 1000,
    "telelogs": 100,
    "telemath": 100,
    "teletables": 100,
    "three_gpp": 100,
    "oranbench": 150,
    "srsranbench": 150,
}

# Full dataset sample counts (from HuggingFace GSMA/ot-full-benchmarks).
_FULL_SAMPLE_COUNT_OVERRIDES: dict[str, int] = {
    "teleqna": 10_000,
    "telelogs": 864,
    "telemath": 500,
    "teletables": 500,
    "three_gpp": 2_000,
    "oranbench": 1_500,
    "srsranbench": 1_500,
}


def get_total_samples(eval_id: str, full: bool = False) -> int:
    """Return the expected sample count for *eval_id*.

    When *full* is ``True`` the count comes from ``_FULL_SAMPLE_COUNT_OVERRIDES``;
    otherwise from the regular ``_SAMPLE_COUNT_OVERRIDES``.
    """
    overrides = _FULL_SAMPLE_COUNT_OVERRIDES if full else _SAMPLE_COUNT_OVERRIDES
    return overrides.get(eval_id, 0)


_FALLBACK_BENCHMARK_IDS: tuple[str, ...] = (
    "teleqna",
    "telelogs",
    "telemath",
    "teletables",
    "three_gpp",
)


def _module_path_for(eval_id: str) -> str:
    return f"evals.{eval_id}.{eval_id}"


def _import_optional(module_path: str) -> ModuleType | None:
    try:
        return import_module(module_path)
    except Exception:
        return None


def _display_name(eval_id: str) -> str:
    override = _NAME_OVERRIDES.get(eval_id)
    if override:
        return override

    words = []
    for token in eval_id.replace("-", "_").split("_"):
        if not token:
            continue
        if token.isdigit():
            words.append(token)
            continue
        lower = token.lower()
        if lower in {"gpp", "ran", "llm", "qa"}:
            words.append(token.upper())
            continue
        words.append(token.capitalize())
    return " ".join(words) if words else eval_id


def _short_name(eval_id: str, name: str) -> str:
    override = _SHORT_NAME_OVERRIDES.get(eval_id)
    if override:
        return override

    parts = [p for p in name.replace("-", " ").split() if p]
    if len(parts) > 1:
        acronym = "".join(p[0].upper() for p in parts if p[0].isalnum())
        if 2 <= len(acronym) <= 6:
            return acronym
    if parts:
        return parts[0][:7]
    return eval_id[:7]


def _description(eval_id: str, name: str) -> str:
    override = _DESCRIPTION_OVERRIDES.get(eval_id)
    if override:
        return override
    return f"{name} evaluation benchmark"


def _hf_column(eval_id: str, module: ModuleType | None) -> str:
    if module is not None:
        dataset_name = getattr(module, "DEFAULT_DATASET_NAME", None)
        if isinstance(dataset_name, str) and dataset_name.strip():
            return dataset_name.strip()
    return eval_id


def _sample_count_from_task(task: object) -> int:
    dataset = getattr(task, "dataset", None)
    if dataset is None:
        return 0

    samples = getattr(dataset, "samples", None)
    if isinstance(samples, int):
        return max(samples, 0)
    if isinstance(samples, (list, tuple, set, dict)):
        return len(samples)
    if samples is not None:
        try:
            return len(samples)
        except TypeError:
            pass
    try:
        return len(dataset)
    except TypeError:
        return 0


def _callable_without_args(task_fn: Callable[..., object]) -> bool:
    try:
        sig = inspect.signature(task_fn)
    except (TypeError, ValueError):
        return False
    for param in sig.parameters.values():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if param.default is inspect.Parameter.empty:
            return False
    return True


def _total_samples(eval_id: str, task_fn: Callable[..., object] | None) -> int:
    override = _SAMPLE_COUNT_OVERRIDES.get(eval_id)
    if override is not None:
        return override

    if task_fn is None or not _callable_without_args(task_fn):
        return 0

    try:
        task = task_fn()
        return _sample_count_from_task(task)
    except Exception as exc:
        _log.debug("Could not infer sample count for %s: %s", eval_id, exc)
        return 0


def _build_config(
    eval_id: str,
    task_fn: Callable[..., object] | None,
) -> BenchmarkConfig:
    module_path = getattr(task_fn, "__module__", _module_path_for(eval_id))
    function_name = getattr(task_fn, "__name__", eval_id)
    module = _import_optional(module_path)
    name = _display_name(eval_id)
    return BenchmarkConfig(
        id=eval_id,
        name=name,
        short_name=_short_name(eval_id, name),
        description=_description(eval_id, name),
        hf_column=_hf_column(eval_id, module),
        module_path=module_path,
        function_name=function_name,
        total_samples=_total_samples(eval_id, task_fn),
    )


def _discover_benchmarks() -> tuple[BenchmarkConfig, ...]:
    try:
        registry_module = import_module("evals._registry")
    except Exception:
        return ()

    eval_ids = getattr(registry_module, "__all__", ())
    if not isinstance(eval_ids, list | tuple):
        return ()

    discovered: list[BenchmarkConfig] = []
    seen: set[str] = set()
    for eval_id in eval_ids:
        if not isinstance(eval_id, str) or not eval_id or eval_id in seen:
            continue
        seen.add(eval_id)
        task_fn = getattr(registry_module, eval_id, None)
        if task_fn is not None and not callable(task_fn):
            task_fn = None
        discovered.append(_build_config(eval_id, task_fn))
    return tuple(discovered)


def _fallback_benchmarks() -> tuple[BenchmarkConfig, ...]:
    return tuple(_build_config(eval_id, None) for eval_id in _FALLBACK_BENCHMARK_IDS)


BENCHMARKS: tuple[BenchmarkConfig, ...] = (
    _discover_benchmarks() or _fallback_benchmarks()
)

BENCHMARKS_BY_ID: dict[str, BenchmarkConfig] = {b.id: b for b in BENCHMARKS}
