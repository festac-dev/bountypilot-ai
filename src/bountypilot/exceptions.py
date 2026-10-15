"""BountyPilot exception hierarchy mapped to documented exit codes."""

from __future__ import annotations

from bountypilot import constants


class BountyPilotError(Exception):
    """Base class for all errors surfaced to the CLI user."""

    exit_code = constants.EXIT_GENERAL
    message = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message


class UsageError(BountyPilotError):
    exit_code = constants.EXIT_USAGE
    message = "Invalid command usage."


class ConfigurationError(BountyPilotError):
    exit_code = constants.EXIT_CONFIG
    message = "Configuration error."


class ValidationError(BountyPilotError):
    exit_code = constants.EXIT_VALIDATION
    message = "Validation failed."


class SecurityPolicyError(BountyPilotError):
    exit_code = constants.EXIT_SECURITY
    message = "Operation blocked by security policy."


# --- Gibwork integration errors (exit code 4 / 5) ---------------------------


class GibworkError(BountyPilotError):
    """Base class for Gibwork integration problems."""

    exit_code = constants.EXIT_INTEGRATION
    message = "Gibwork integration error."


class GibworkNotConfigured(GibworkError):
    exit_code = constants.EXIT_CONFIG
    message = "Gibwork integration is not configured."


class GibworkAuthenticationRequired(GibworkError):
    exit_code = constants.EXIT_INTEGRATION
    message = "Gibwork authentication is required for this operation."


class GibworkUnavailable(GibworkError):
    exit_code = constants.EXIT_SERVICE_UNAVAILABLE
    message = "Gibwork service is temporarily unavailable."


class GibworkRateLimited(GibworkUnavailable):
    message = "Gibwork rate limit reached; retry later."


class GibworkInvalidResponse(GibworkError):
    message = "Gibwork returned an unexpected response."


class GibworkUnsupportedOperation(GibworkError):
    message = "This operation is not supported by the configured Gibwork integration."


class GibworkNotFound(GibworkError):
    message = "Bounty not found on Gibwork."


# --- Storage errors ----------------------------------------------------------


class StorageError(BountyPilotError):
    message = "Local storage error."


class DatabaseCorruptionError(StorageError):
    message = "Local database appears to be corrupted."


class DuplicateRecordError(StorageError):
    message = "Record already exists."
