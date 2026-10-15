"""Stable constants shared across BountyPilot."""

APP_NAME = "bountypilot"
VERSION_FILE_ANNOTATION = "bountypilot"

# Tracked opportunity lifecycle (section 6.4 of the build spec). Ordered.
TRACK_STATUSES = (
    "saved",
    "evaluating",
    "planned",
    "in progress",
    "blocked",
    "completed",
    "abandoned",
)

# Allowed transitions: current status -> set of statuses it may move to.
TRACK_STATUS_TRANSITIONS = {
    "saved": {"evaluating", "planned", "abandoned"},
    "evaluating": {"planned", "saved", "abandoned"},
    "planned": {"in progress", "evaluating", "abandoned"},
    "in progress": {"blocked", "completed", "planned", "abandoned"},
    "blocked": {"in progress", "abandoned"},
    "completed": set(),
    "abandoned": {"saved"},
}

# Documented exit-code scheme (section 10 of the build spec).
EXIT_OK = 0
EXIT_GENERAL = 1
EXIT_USAGE = 2
EXIT_CONFIG = 3
EXIT_INTEGRATION = 4
EXIT_SERVICE_UNAVAILABLE = 5
EXIT_VALIDATION = 6
EXIT_SECURITY = 7

# Configuration keys accepted by `bountypilot config set`.
# "secret": value is redacted in `config show` and logs.
CONFIG_KEYS: dict = {
    "GIBWORK_INTEGRATION_MODE": {
        "default": "public_api",
        "choices": ("public_api", "official_cli"),
    },
    "GIBWORK_BASE_URL": {"default": "https://api.gib.work", "secret": False},
    "GIBWORK_CLI_PATH": {"default": "", "secret": False},
    "GIBWORK_TIMEOUT_SECONDS": {"default": 20, "type": int, "min": 1, "max": 120},
    "GIBWORK_RETRY_LIMIT": {"default": 2, "type": int, "min": 0, "max": 5},
    "GIBWORK_REQUEST_INTERVAL_SECONDS": {"default": 1.0, "type": float, "min": 0.0, "max": 60.0},
    "GIBWORK_API_KEY": {"default": "", "secret": True},
    "AI_PROVIDER": {"default": "local", "choices": ("local", "remote")},
    "LOCAL_MODEL_NAME": {"default": "bountypilot-heuristic-v1", "secret": False},
    "AI_API_KEY": {"default": "", "secret": True},
    "AI_BASE_URL": {"default": "", "secret": False},
    "AI_MODEL": {"default": "", "secret": False},
    "DATABASE_URL": {"default": "", "secret": False},
    "LOG_LEVEL": {"default": "WARNING", "choices": ("DEBUG", "INFO", "WARNING", "ERROR")},
    "OUTPUT_FORMAT": {"default": "table", "choices": ("table", "json")},
    "REQUEST_TIMEOUT_SECONDS": {"default": 20, "type": int, "min": 1, "max": 120},
    "MAX_RETRIES": {"default": 2, "type": int, "min": 0, "max": 5},
    "DATA_DIRECTORY": {"default": "", "secret": False},
}

CONFIG_KEY_NAMES = tuple(CONFIG_KEYS)

SECRET_ENV_SUFFIXES = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY")

# Environments where the user config lives by default.
USER_CONFIG_FILE = "config.json"
USER_DB_FILE = "bountypilot.db"
USER_EVIDENCE_DIR = "evidence"
USER_EXPORT_DIR = "exports"
