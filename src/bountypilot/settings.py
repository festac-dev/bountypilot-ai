"""Configuration management.

Precedence (highest first):
  1. command-line overrides
  2. environment variables
  3. user config file (<data directory>/config.json)
  4. safe defaults

Secrets are never printed by `config show`; see security/redaction.py.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from bountypilot import constants
from bountypilot.constants import CONFIG_KEYS
from bountypilot.exceptions import ConfigurationError

_BOOL_TRUE = {"1", "true", "yes", "on"}


def _coerce(key: str, raw: Any) -> Any:
    spec: dict[str, Any] = CONFIG_KEYS[key]
    value: Any
    if "choices" in spec:
        value = str(raw).strip()
        matches = [c for c in spec["choices"] if c.lower() == value.lower()]
        if not matches:
            raise ConfigurationError(f"Invalid value for {key}: {raw!r}. Allowed: {', '.join(spec['choices'])}")
        return matches[0]
    if spec.get("type") is int:
        try:
            value = int(str(raw).strip())
        except ValueError as exc:
            raise ConfigurationError(f"{key} must be an integer, got {raw!r}") from exc
    elif spec.get("type") is float:
        try:
            value = float(str(raw).strip())
        except ValueError as exc:
            raise ConfigurationError(f"{key} must be a number, got {raw!r}") from exc
    else:
        value = str(raw)
    if "min" in spec and value < spec["min"]:
        raise ConfigurationError(f"{key} must be >= {spec['min']}")
    if "max" in spec and value > spec["max"]:
        raise ConfigurationError(f"{key} must be <= {spec['max']}")
    return value


def default_data_directory() -> Path:
    """Per-user data directory, overridable via BOUNTYPILOT_DATA_DIRECTORY."""
    env = os.environ.get("BOUNTYPILOT_DATA_DIRECTORY", "").strip()
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        base = Path(xdg).expanduser()
    else:
        base = Path.home() / ".local" / "share"
    return base / "bountypilot"


@dataclass
class Settings:
    """Effective configuration with provenance per key."""

    values: dict[str, Any]
    sources: dict[str, str]

    # Typed convenience accessors ------------------------------------------
    @property
    def gibwork_base_url(self) -> str:
        return str(self.values["GIBWORK_BASE_URL"]).rstrip("/")

    @property
    def gibwork_timeout(self) -> float:
        return float(self.values["GIBWORK_TIMEOUT_SECONDS"])

    @property
    def gibwork_retries(self) -> int:
        return int(self.values["GIBWORK_RETRY_LIMIT"])

    @property
    def gibwork_request_interval(self) -> float:
        return float(self.values["GIBWORK_REQUEST_INTERVAL_SECONDS"])

    @property
    def gibwork_api_key(self) -> str:
        return str(self.values["GIBWORK_API_KEY"])

    @property
    def gibwork_integration_mode(self) -> str:
        return str(self.values["GIBWORK_INTEGRATION_MODE"])

    @property
    def gibwork_cli_path(self) -> str:
        return str(self.values["GIBWORK_CLI_PATH"])

    @property
    def ai_provider(self) -> str:
        return str(self.values["AI_PROVIDER"])

    @property
    def data_directory(self) -> Path:
        raw = str(self.values["DATA_DIRECTORY"]).strip()
        return Path(raw).expanduser() if raw else default_data_directory()

    @property
    def database_path(self) -> Path:
        raw = str(self.values["DATABASE_URL"]).strip()
        if raw.startswith("sqlite:///"):
            return Path(raw[len("sqlite:///") :]).expanduser()
        return self.data_directory / constants.USER_DB_FILE

    @property
    def output_format(self) -> str:
        return str(self.values["OUTPUT_FORMAT"])

    @property
    def log_level(self) -> str:
        return str(self.values["LOG_LEVEL"])

    def as_redacted_dict(self) -> dict[str, str]:
        from bountypilot.security.redaction import redact_value

        return {k: redact_value(k, v) for k, v in sorted(self.values.items())}


class ConfigFile:
    """JSON-backed user config file with restrictive permissions."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Cannot read config file {self.path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigurationError(f"Config file {self.path} must contain a JSON object.")
        return data

    def save(self, values: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600 - user-only
        except OSError:  # pragma: no cover - filesystems without chmod (e.g. some Termux)
            pass
        os.replace(tmp, self.path)

    def set_key(self, key: str, value: Any) -> None:
        data = self.load()
        data[key] = value
        self.save(data)


def _load_env_file(directory: Path) -> None:
    """Minimal .env loader so `bountypilot init` users get documented behaviour."""
    env_file = directory / ".env"
    if not env_file.exists():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


def load_settings(
    overrides: Optional[dict[str, Any]] = None,
    data_directory: Optional[Path] = None,
    load_dotenv: bool = True,
) -> Settings:
    """Build effective settings from all sources with precedence."""
    if data_directory is None:
        # Resolution: command-line override > env DATA_DIRECTORY > env
        # BOUNTYPILOT_DATA_DIRECTORY > per-user default.
        override_dir = str((overrides or {}).get("DATA_DIRECTORY") or "").strip()
        if override_dir:
            data_directory = Path(override_dir).expanduser()
        else:
            env_data_dir = os.environ.get("DATA_DIRECTORY", "").strip()
            data_directory = Path(env_data_dir).expanduser() if env_data_dir else default_data_directory()
        if load_dotenv:
            _load_env_file(Path.cwd())

    values: dict[str, Any] = {k: spec["default"] for k, spec in CONFIG_KEYS.items()}
    sources: dict[str, str] = {k: "default" for k in CONFIG_KEYS}

    def apply_from(key: str, raw: Any, source: str) -> None:
        try:
            values[key] = _coerce(key, raw)
            sources[key] = source
        except ConfigurationError:
            if source != "environment":
                raise

    config_file = ConfigFile(Path(data_directory) / constants.USER_CONFIG_FILE)
    file_values = config_file.load()
    for key, raw in file_values.items():
        if key in CONFIG_KEYS:
            apply_from(key, raw, f"config file ({config_file.path})")

    for key in CONFIG_KEYS:
        env_value = os.environ.get(key)
        if env_value is not None and env_value != "":
            apply_from(key, env_value, "environment")

    for key, raw in (overrides or {}).items():
        if key in CONFIG_KEYS and raw is not None:
            apply_from(key, raw, "command line")

    # The runtime data directory always wins so the process stays self-consistent.
    values["DATA_DIRECTORY"] = str(data_directory)
    sources["DATA_DIRECTORY"] = "runtime"

    return Settings(values=values, sources=sources)


def validate_setting_key(key: str) -> str:
    key = key.strip().upper()
    if key not in CONFIG_KEYS:
        raise ConfigurationError(
            f"Unknown configuration key: {key}. Supported keys: {', '.join(constants.CONFIG_KEY_NAMES)}"
        )
    return key


def set_setting(settings: Settings, key: str, value: str) -> None:
    """Validate and persist a setting to the user config file."""
    key = validate_setting_key(key)
    coerced = _coerce(key, value)
    config_file = ConfigFile(settings.data_directory / constants.USER_CONFIG_FILE)
    config_file.set_key(key, coerced)
