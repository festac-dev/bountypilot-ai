"""Safe subprocess execution.

Rules (security section of the build spec):
- argument arrays only; never shell=True with user input
- explicit executable paths
- timeouts and output size bounds
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from bountypilot.exceptions import SecurityPolicyError
from bountypilot.logging_config import get_logger

MAX_OUTPUT_BYTES = 2_000_000  # 2 MB hard bound on captured output

log = get_logger("bountypilot.security")


@dataclass
class CommandResult:
    ok: bool
    exit_code: Optional[int]
    stdout: str
    stderr: str
    timed_out: bool


def run_command(
    argv: Sequence[str],
    cwd: Optional[Path] = None,
    timeout_seconds: int = 120,
    env_overrides: Optional[dict[str, str]] = None,
) -> CommandResult:
    """Run a command with argument arrays and bounded output. Never uses a shell."""
    if not argv or not isinstance(argv, (list, tuple)):
        raise SecurityPolicyError("run_command requires a non-empty argv list.")
    executable = Path(argv[0])
    if executable.name != str(argv[0]) and not executable.exists():
        log.debug("executable not found: %s", argv[0])
        return CommandResult(
            ok=False,
            exit_code=None,
            stdout="",
            stderr=f"executable not found: {argv[0]}",
            timed_out=False,
        )
    log.debug("running subprocess: %s", argv[0])
    env = None
    if env_overrides:
        import os

        env = dict(os.environ)
        env.update(env_overrides)
    try:
        completed = subprocess.run(  # noqa: S603 - argv array, no shell
            [str(a) for a in argv],
            cwd=str(cwd) if cwd else None,
            timeout=timeout_seconds,
            capture_output=True,
            env=env,
        )
        return CommandResult(
            ok=completed.returncode == 0,
            exit_code=completed.returncode,
            stdout=completed.stdout.decode("utf-8", "replace")[:MAX_OUTPUT_BYTES],
            stderr=completed.stderr.decode("utf-8", "replace")[:MAX_OUTPUT_BYTES],
            timed_out=False,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(ok=False, exit_code=None, stdout="", stderr="", timed_out=True)
    except FileNotFoundError:
        return CommandResult(ok=False, exit_code=None, stdout="", stderr="executable not found", timed_out=False)
