"""Security tests: redaction, path safety, subprocess policy, file permissions."""

from __future__ import annotations

import logging
import stat

from bountypilot.exceptions import SecurityPolicyError
from bountypilot.logging_config import RedactingFilter
from bountypilot.security.command_execution import run_command
from bountypilot.security.path_validation import (
    ensure_directory,
    secure_temp_file,
    write_private_file,
)


def test_log_filter_redacts_secrets():
    filt = RedactingFilter()
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "key=supersecret123", None, None)
    assert filt.filter(record) is True
    assert "supersecret123" not in record.msg


def test_secure_temp_file_is_restricted_and_removed(tmp_path):
    with secure_temp_file(directory=tmp_path) as path:
        assert path.exists()
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode & 0o077 == 0
        path.write_text("data")
    assert not path.exists()


def test_write_private_file_mode(tmp_path):
    target = tmp_path / "secret.json"
    write_private_file(target, '{"k": "v"}')
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode & 0o077 == 0
    assert target.read_text() == '{"k": "v"}'


def test_ensure_directory_restrictive(tmp_path):
    directory = ensure_directory(tmp_path / "new" / "nested")
    assert directory.is_dir()
    assert stat.S_IMODE(directory.stat().st_mode) & 0o077 == 0


def test_run_command_rejects_shell_strings():
    import pytest

    with pytest.raises(SecurityPolicyError):
        run_command("echo hello; rm -rf /")  # type: ignore[arg-type]
    with pytest.raises(SecurityPolicyError):
        run_command([])


def test_run_command_runs_simple_program(tmp_path):
    result = run_command(["python3", "-c", "print('hello')"], cwd=tmp_path, timeout_seconds=10)
    assert result.ok
    assert "hello" in result.stdout


def test_run_command_timeout(tmp_path):
    result = run_command(["python3", "-c", "import time; time.sleep(5)"], cwd=tmp_path, timeout_seconds=1)
    assert result.timed_out is True
    assert result.ok is False


def test_run_command_missing_executable():
    result = run_command(["/nonexistent/binary-xyz", "--version"])
    assert result.ok is False
    assert result.exit_code is None
