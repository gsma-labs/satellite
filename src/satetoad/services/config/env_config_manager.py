from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from satetoad.examples.eval_data import MODEL_PROVIDERS


@dataclass
class ModelConfig:
    """A model configured by the user."""

    provider: str
    model: str
    api_key: str = ""

_PROXY_PREFIXES = frozenset({"openrouter", "bedrock", "vertex", "azureai"})

# Precomputed lookups
_PROVIDERS_BY_ID = {p["id"]: p for p in MODEL_PROVIDERS}
_PROVIDER_ENV_VARS = {p["id"]: p.get("env_var", "") for p in MODEL_PROVIDERS}
_PREFIX_TO_PROVIDER = {p["model_prefix"]: p["id"] for p in MODEL_PROVIDERS if p.get("model_prefix")}


def normalize_model_path(model_string: str) -> str:
    """Strip proxy prefixes (openrouter, bedrock, vertex, azureai) from model string."""
    parts = model_string.lower().strip("/").split("/")
    if not parts:
        return model_string
    if parts[0] in _PROXY_PREFIXES:
        parts = parts[1:]
    return "/".join(parts)


class EnvConfigManager:
    """Manages .env file persistence for models and API keys."""

    def __init__(self, env_path: Path) -> None:
        self._env_path = env_path

    def _format_value(self, value: str) -> str:
        """Format value for .env file with appropriate quoting."""
        if "\n" in value or "\r" in value:
            raise ValueError("Values cannot contain newlines")
        # Single quotes if no single quotes in value, double quotes otherwise
        if "'" not in value:
            return f"'{value}'"
        # Double-quote: escape \, $, "
        escaped = value.replace("\\", "\\\\").replace("$", "\\$").replace('"', '\\"')
        return f'"{escaped}"'

    def _read_env(self) -> dict[str, str]:
        """Read .env file into dict. Always reads from disk for external edit support."""
        if not self._env_path.exists():
            return {}
        return {k: v for k, v in dotenv_values(self._env_path).items() if v is not None}

    def _write_env(self, env_vars: dict[str, str]) -> None:
        """Write dict to .env file with proper quoting."""
        lines = [f"{key}={self._format_value(value)}" for key, value in env_vars.items()]
        self._env_path.write_text("\n".join(lines) + "\n")

    def load_models(self) -> list[ModelConfig]:
        """Load models from INSPECT_EVAL_MODEL."""
        env_vars = self._read_env()
        inspect_model = env_vars.get("INSPECT_EVAL_MODEL", "")
        if not inspect_model:
            return []

        models: list[ModelConfig] = []
        for model_string in (m.strip() for m in inspect_model.split(",") if m.strip()):
            provider_id = next(
                (pid for prefix, pid in _PREFIX_TO_PROVIDER.items() if model_string.startswith(prefix)),
                None
            )
            if provider_id is None:
                continue
            env_var = _PROVIDER_ENV_VARS.get(provider_id, "")
            models.append(ModelConfig(
                provider=provider_id,
                model=model_string,
                api_key=env_vars.get(env_var, "") if env_var else ""
            ))
        return models

    def save_models(self, configs: list[ModelConfig]) -> None:
        """Save models to INSPECT_EVAL_MODEL. Also saves base URLs for local providers."""
        env_vars = self._read_env()

        env_vars.pop("INSPECT_EVAL_MODEL", None)
        if configs:
            env_vars["INSPECT_EVAL_MODEL"] = ",".join(c.model for c in configs)

        # Save base URLs for local providers (deduplicate by provider, keep last)
        for config in configs:
            provider = _PROVIDERS_BY_ID.get(config.provider, {})
            env_var = _PROVIDER_ENV_VARS.get(config.provider)
            is_base_url = provider.get("credential_type") == "base_url"
            if is_base_url and env_var and config.api_key:
                env_vars[env_var] = config.api_key

        self._write_env(env_vars)

    def get_all_vars(self) -> dict[str, str]:
        """Get all env vars from .env file."""
        return self._read_env()

    def set_var(self, name: str, value: str) -> None:
        """Set or update an env var."""
        env_vars = self._read_env()
        env_vars[name] = value
        self._write_env(env_vars)

    def delete_var(self, name: str) -> bool:
        """Delete an env var. Returns True if deleted."""
        env_vars = self._read_env()
        if name not in env_vars:
            return False
        del env_vars[name]
        self._write_env(env_vars)
        return True
