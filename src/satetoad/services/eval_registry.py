"""Evaluation registry service.

Provides dynamic loading of available evaluations from the otelcos/evals
package registry, with local metadata for display names and descriptions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvalInfo:
    """Evaluation metadata.

    Attributes:
        id: Unique identifier matching the registry (e.g., "teleqna")
        name: Display name (e.g., "TeleQnA")
        short_name: Short name for leaderboard columns (e.g., "QnA")
        description: Description of what the eval tests
        hf_column: Column name in HuggingFace leaderboard dataset
    """

    id: str
    name: str
    short_name: str
    description: str
    hf_column: str

    def to_dict(self) -> dict:
        """Convert to dictionary format compatible with BENCHMARKS structure."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }


# Metadata for each eval (validated against registry at runtime)
EVAL_METADATA: dict[str, dict] = {
    "teleqna": {
        "name": "TeleQnA",
        "short_name": "QnA",
        "description": "Question answering benchmark for telecom domain",
        "hf_column": "teleqna",
    },
    "telelogs": {
        "name": "TeleLogs",
        "short_name": "Logs",
        "description": "Log analysis and troubleshooting benchmark",
        "hf_column": "telelogs",
    },
    "telemath": {
        "name": "TeleMath",
        "short_name": "Math",
        "description": "Mathematical reasoning for telecom calculations",
        "hf_column": "telemath",
    },
    "teletables": {
        "name": "TeleTables",
        "short_name": "Tables",
        "description": "Table understanding and extraction benchmark",
        "hf_column": "teletables",
    },
    "three_gpp": {
        "name": "3GPP",
        "short_name": "3GPP",
        "description": "3GPP specification understanding benchmark",
        "hf_column": "3gpp_tsg",
    },
}


def _get_registry_evals() -> list[str]:
    """Get eval IDs from otelcos/evals registry.

    Uses lazy import to avoid loading inspect-ai at app startup.
    The import happens when modals call get_benchmarks(), by which point
    Textual has full terminal control and inspect-ai won't interfere.

    Returns:
        List of eval IDs from the registry, or fallback to EVAL_METADATA keys
        if the evals package is not installed.
    """
    try:
        from evals._registry import __all__ as registry_evals

        return list(registry_evals)
    except ImportError:
        logger.warning("evals package not installed, using fallback metadata")
        return list(EVAL_METADATA.keys())


def get_available_evals() -> list[EvalInfo]:
    """Get available evals from registry with metadata.

    Returns evals that exist in both the registry and EVAL_METADATA.
    Logs warnings for registry evals missing metadata.

    Returns:
        List of EvalInfo objects for available evaluations.
    """
    registry_ids = _get_registry_evals()

    # Warn about missing metadata for new evals
    for eval_id in registry_ids:
        if eval_id not in EVAL_METADATA:
            logger.warning(
                f"No metadata for eval '{eval_id}' - add to EVAL_METADATA in eval_registry.py"
            )

    # Return evals that have metadata, preserving registry order
    return [
        EvalInfo(id=eval_id, **EVAL_METADATA[eval_id])
        for eval_id in registry_ids
        if eval_id in EVAL_METADATA
    ]


def get_benchmarks() -> list[dict]:
    """Get benchmarks in dict format for backward compatibility.

    Returns:
        List of benchmark dictionaries with id, name, and description.
    """
    return [eval_info.to_dict() for eval_info in get_available_evals()]
