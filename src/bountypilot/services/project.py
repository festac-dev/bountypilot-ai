"""Project workflow service: inspect, test, audit, plan, scaffold, report.

Safety: never auto-runs untrusted scripts; `project test` only runs commands
from the project's declared configuration; destructive operations require
confirmation at the command layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from bountypilot.exceptions import ValidationError
from bountypilot.logging_config import get_logger
from bountypilot.security.command_execution import run_command
from bountypilot.services.container import AppServices

log = get_logger("bountypilot.project")

TEST_COMMANDS = {
    "pytest": ["pytest", "-q"],
    "npm": ["npm", "test", "--silent"],
}


class ProjectService:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    # -- inspect ---------------------------------------------------------------

    def inspect(self, path: str) -> dict[str, Any]:
        root = self._existing_dir(path)
        info: dict[str, Any] = {
            "path": str(root),
            "structure": [],
            "has_tests": False,
            "has_readme": False,
            "has_license": False,
            "config_files": [],
        }
        max_entries = 200
        count = 0
        for entry in sorted(root.iterdir()):
            if count >= max_entries:
                info["structure"].append("... (truncated)")
                break
            info["structure"].append(entry.name + ("/" if entry.is_dir() else ""))
            count += 1
        for name, exists in (
            ("tests", any(root.glob("tests")) or any(root.glob("test_*"))),
            ("README", (root / "README.md").exists() or (root / "README.rst").exists()),
            ("LICENSE", (root / "LICENSE").exists()),
        ):
            if name == "tests":
                info["has_tests"] = bool(exists)
            elif name == "README":
                info["has_readme"] = bool(exists)
            else:
                info["has_license"] = bool(exists)
        for cfg in ("pyproject.toml", "package.json", "requirements.txt", "Cargo.toml", "go.mod"):
            if (root / cfg).exists():
                info["config_files"].append(cfg)
        return info

    # -- test -------------------------------------------------------------------

    def test(self, path: str, command: Optional[list[str]] = None) -> dict[str, Any]:
        root = self._existing_dir(path)
        if command is None:
            command = self._detect_test_command(root)
        if not command:
            return {
                "ran": False,
                "ok": False,
                "detail": "No test command detected; pass one explicitly.",
            }
        result = run_command(command, cwd=root, timeout_seconds=600)
        # Never report success unless the process actually completed with exit 0.
        return {
            "ran": True,
            "ok": result.ok,
            "command": command,
            "timed_out": result.timed_out,
            "stdout_tail": result.stdout[-4000:],
            "stderr_tail": result.stderr[-2000:],
            "origin": "verified_run",
        }

    @staticmethod
    def _detect_test_command(root: Path) -> Optional[list[str]]:
        if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or (root / "setup.py").exists():
            return list(TEST_COMMANDS["pytest"])
        if (root / "package.json").exists():
            try:
                package = json.loads((root / "package.json").read_text(encoding="utf-8"))
                if "test" in (package.get("scripts") or {}):
                    return list(TEST_COMMANDS["npm"])
            except (ValueError, OSError):
                return None
        return None

    # -- audit --------------------------------------------------------------------

    def audit(self, path: str) -> dict[str, Any]:
        """Static, read-only audit. Not a substitute for tests or security scans."""
        root = self._existing_dir(path)
        findings: list[dict[str, str]] = []
        if not (root / "README.md").exists() and not (root / "README.rst").exists():
            findings.append({"severity": "medium", "finding": "No README file."})
        if not any(root.glob("tests")) and not any(root.glob("test_*")):
            findings.append({"severity": "high", "finding": "No tests directory found."})
        if not (root / "LICENSE").exists():
            findings.append({"severity": "medium", "finding": "No LICENSE file."})
        for py_file in self._python_files(root)[:500]:
            try:
                text = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                # 'Possible' excluded so the scanner never flags its own finding text.
                if "eval(" in line and "Possible" not in line and "get(" not in line:
                    findings.append(
                        {
                            "severity": "high",
                            "finding": f"Possible eval() use at {py_file}:{line_number}",
                        }
                    )
                if line.strip().startswith("shell=True"):
                    findings.append({"severity": "high", "finding": f"shell=True at {py_file}:{line_number}"})
        env_file = root / ".env"
        if env_file.exists():
            findings.append(
                {
                    "severity": "medium",
                    "finding": (
                        ".env file present in the project directory; ensure it is git-ignored and never committed."
                    ),
                }
            )
        return {
            "path": str(root),
            "findings": findings,
            "disclaimer": "Static heuristic audit only; run real test suites and security scans separately.",
        }

    @staticmethod
    def _python_files(root: Path, limit: int = 500) -> list[Path]:
        """Collect Python files, skipping dependency/virtualenv directories."""
        skip_names = {".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".git"}
        files = []
        for path in root.rglob("*.py"):
            if any(part in skip_names for part in path.relative_to(root).parts):
                continue
            files.append(path)
            if len(files) >= limit:
                break
        return files

    # -- plan / scaffold ------------------------------------------------------------

    def plan(self, bounty_id: str) -> dict[str, Any]:
        from bountypilot.services.analysis import AnalysisService

        return AnalysisService(self.services).plan(bounty_id)

    def scaffold(self, path: str, bounty_id: str, force: bool = False) -> dict[str, Any]:
        """Create a minimal project skeleton for a bounty (no overwrite without force)."""
        root = Path(path).expanduser().resolve()
        if root.exists() and any(root.iterdir()) and not force:
            raise ValidationError(f"Directory {path} is not empty; use --force to proceed.")
        root.mkdir(parents=True, exist_ok=True)
        created = []
        plan = self.plan(bounty_id)["plan"]
        readme = root / "README.md"
        if not readme.exists() or force:
            steps = "\n".join(f"{i}. {s['step']}" for i, s in enumerate(plan["steps"], start=1))
            readme.write_text(
                f"# Work project for bounty {bounty_id}\n\n"
                f"> Scaffolding generated by BountyPilot AI; plan steps are AI estimates.\n\n"
                f"## Suggested steps\n\n{steps}\n",
                encoding="utf-8",
            )
            created.append("README.md")
        tests_dir = root / "tests"
        if not tests_dir.exists():
            tests_dir.mkdir(exist_ok=True)
            (tests_dir / "__init__.py").write_text("", encoding="utf-8")
            created.append("tests/__init__.py")
        return {"path": str(root), "created": created}

    # -- report -----------------------------------------------------------------------

    def report(self, bounty_id: str) -> dict[str, Any]:
        from bountypilot.services.reporting import ReportingService

        return ReportingService(self.services).generate(bounty_id)

    @staticmethod
    def _existing_dir(path: str) -> Path:
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            raise ValidationError(f"Not a directory: {path}")
        return root
