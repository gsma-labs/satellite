"""EvalSettings - Configuration for inspect-ai evaluation parameters."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar

DEFAULT_SETTINGS_PATH = Path.home() / ".satellite" / "eval_settings.json"


@dataclass
class EvalSettings:
    """Configuration for inspect-ai eval_set parameters."""

    DEFAULT_EPOCHS: ClassVar[int] = 1
    DEFAULT_MAX_CONNECTIONS: ClassVar[int] = 10

    limit: int | None = None
    epochs: int = DEFAULT_EPOCHS
    max_connections: int = DEFAULT_MAX_CONNECTIONS
    token_limit: int | None = None
    message_limit: int | None = None
    full_benchmark: bool = False


class EvalSettingsManager:
    """Manages eval settings persistence to JSON file."""

    def __init__(self, settings_path: Path = DEFAULT_SETTINGS_PATH) -> None:
        self._path = settings_path

    def load(self) -> EvalSettings:
        """Load settings from disk. Returns defaults if file missing."""
        if not self._path.exists():
            return EvalSettings()
        data = json.loads(self._path.read_text())
        defaults = EvalSettings()
        return EvalSettings(
            limit=data.get("limit"),
            epochs=data.get("epochs", defaults.epochs),
            max_connections=data.get("max_connections", defaults.max_connections),
            token_limit=data.get("token_limit"),
            message_limit=data.get("message_limit"),
            full_benchmark=data.get("full_benchmark", False),
        )

    def save(self, settings: EvalSettings) -> None:
        """Save settings to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(asdict(settings), indent=2) + "\n")
