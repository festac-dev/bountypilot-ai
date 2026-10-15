"""Submission readiness checking and packaging.

Never auto-submits anything; never claims a submission happened. Owner-only
manual items (Discord sessions, Hackathon role, demo video, public repo) are
recorded as user attestations, never verified facts.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any

from bountypilot.core import validation
from bountypilot.core.validation import safe_output_path
from bountypilot.exceptions import ValidationError
from bountypilot.security.path_validation import ensure_directory
from bountypilot.services.container import AppServices

# Items the Gibwork Developer Hackathon bounty requires, with how BountyPilot
# can check each one. `verified_by` states the evidence source honestly.
CHECKLIST: list[dict[str, str]] = [
    {
        "item": "Public GitHub repository URL",
        "verified_by": "user-supplied URL (format-checked only)",
    },
    {"item": "Source code", "verified_by": "presence of the local project directory"},
    {
        "item": "README with written summary (use case / value / toolset used)",
        "verified_by": "README present and contains the summary heading",
    },
    {
        "item": "Setup and dependency instructions",
        "verified_by": "README contains an Installation section",
    },
    {
        "item": "Environment variable documentation",
        "verified_by": "README mentions environment variables",
    },
    {
        "item": "Commands to run and test the project",
        "verified_by": "README contains usage/test commands",
    },
    {"item": "Sample input/output", "verified_by": "README contains a sample output section"},
    {"item": "Screenshots", "verified_by": "files present in the screenshots directory"},
    {"item": "Demo video URL", "verified_by": "user-supplied URL (placeholder counts as missing)"},
    {"item": "Exported deliverables", "verified_by": "generated report/evidence artifacts found"},
    {
        "item": "Known limitations documented",
        "verified_by": "README contains a limitations section",
    },
    {
        "item": "Discord sessions attended (>=2)",
        "verified_by": "user attestation only - never verified",
    },
    {
        "item": "Hackathon Discord role awarded",
        "verified_by": "user attestation only - never verified",
    },
    {"item": "Google form submission", "verified_by": "user attestation only - never verified"},
]

OWNER_ONLY_ITEMS = (
    "Attend at least 2 hackathon sessions on Discord (manual task).",
    "Obtain the Hackathon Discord role (manual task).",
    "Create the public GitHub repository (manual task).",
    "Record the demo video (manual task).",
    "Capture real screenshots (manual task; BountyPilot can register supplied files as evidence).",
    "Submit the Google form (manual task).",
)


class SubmissionService:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    def check(
        self,
        bounty_id: str,
        repo_url: str = "",
        demo_video_url: str = "",
        project_path: str = "",
        discord_sessions_attended: bool = False,
        hackathon_role_awarded: bool = False,
        form_submitted: bool = False,
    ) -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        if repo_url and not repo_url.startswith(("https://github.com/", "http://github.com/")):
            raise ValidationError("repo_url must be a GitHub repository URL.")
        if demo_video_url and not demo_video_url.startswith(("http://", "https://")):
            raise ValidationError("demo_video_url must be an http(s) URL.")
        self.services.bounties.get(bounty_id)
        screenshots_dir = Path("screenshots")
        screenshots = [p.name for p in screenshots_dir.glob("*") if p.is_file()] if screenshots_dir.exists() else []
        exports_dir = self.services.settings.data_directory / "exports"
        exports = [p.name for p in exports_dir.glob("*") if p.is_file()] if exports_dir.exists() else []
        evidence = [e.to_dict() for e in self.services.evidence.list() if e.bounty_id == bounty_id]

        readme_ok = {
            "summary": False,
            "installation": False,
            "env": False,
            "commands": False,
            "sample": False,
            "limitations": False,
        }
        readme_path = Path("README.md")
        if readme_path.exists():
            text = readme_path.read_text(encoding="utf-8", errors="replace").lower()
            readme_ok = {
                "summary": "gibwork toolset used" in text or "use case" in text,
                "installation": "installation" in text,
                "env": "environment variable" in text or ".env.example" in text,
                "commands": "bountypilot " in text,
                "sample": "sample" in text or "example output" in text,
                "limitations": "limitation" in text,
            }

        def readme_checked(key: str) -> bool:
            if project_path:
                project_readme = Path(project_path) / "README.md"
                if project_readme.exists():
                    ptext = project_readme.read_text(encoding="utf-8", errors="replace").lower()
                    if key == "summary":
                        return "gibwork toolset used" in ptext or "use case" in ptext
                    if key == "installation":
                        return "installation" in ptext
                    if key == "env":
                        return "environment variable" in ptext or ".env.example" in ptext
                    if key == "commands":
                        return "bountypilot " in ptext
                    if key == "sample":
                        return "sample" in ptext
                    if key == "limitations":
                        return "limitation" in ptext
            return readme_ok[key]

        results = [
            {
                "item": CHECKLIST[0]["item"],
                "ok": bool(repo_url),
                "evidence": repo_url or "not supplied",
            },
            {
                "item": CHECKLIST[1]["item"],
                "ok": bool(project_path and Path(project_path).is_dir()),
                "evidence": project_path or "project path not supplied",
            },
            {
                "item": CHECKLIST[2]["item"],
                "ok": readme_checked("summary"),
                "evidence": "README heading check",
            },
            {
                "item": CHECKLIST[3]["item"],
                "ok": readme_checked("installation"),
                "evidence": "README section check",
            },
            {
                "item": CHECKLIST[4]["item"],
                "ok": readme_checked("env") or Path(".env.example").exists(),
                "evidence": "README/.env.example check",
            },
            {
                "item": CHECKLIST[5]["item"],
                "ok": readme_checked("commands"),
                "evidence": "README command check",
            },
            {
                "item": CHECKLIST[6]["item"],
                "ok": readme_checked("sample"),
                "evidence": "README sample check",
            },
            {
                "item": CHECKLIST[7]["item"],
                "ok": bool(screenshots),
                "evidence": ", ".join(screenshots) if screenshots else "screenshots/ is empty",
            },
            {
                "item": CHECKLIST[8]["item"],
                "ok": bool(demo_video_url),
                "evidence": demo_video_url or "not supplied (placeholder does not count)",
            },
            {
                "item": CHECKLIST[9]["item"],
                "ok": bool(exports or evidence),
                "evidence": f"{len(exports)} export(s), {len(evidence)} evidence record(s)",
            },
            {
                "item": CHECKLIST[10]["item"],
                "ok": readme_checked("limitations"),
                "evidence": "README section check",
            },
            {
                "item": CHECKLIST[11]["item"],
                "ok": bool(discord_sessions_attended),
                "evidence": "user attestation (unverified)",
            },
            {
                "item": CHECKLIST[12]["item"],
                "ok": bool(hackathon_role_awarded),
                "evidence": "user attestation (unverified)",
            },
            {
                "item": CHECKLIST[13]["item"],
                "ok": bool(form_submitted),
                "evidence": "user attestation (unverified)",
            },
        ]
        passed = sum(1 for r in results if r["ok"])
        return {
            "bounty_id": bounty_id,
            "checks": results,
            "passed": passed,
            "total": len(results),
            "ready": passed == len(results),
            "owner_only_manual_tasks": list(OWNER_ONLY_ITEMS),
            "disclaimer": "Readiness is evidence-based only. BountyPilot never submits anything and never "
            "attests manual items on your behalf.",
        }

    def package(self, bounty_id: str, output_dir: str = "") -> dict[str, Any]:
        """Create an organized submission package archive from local artifacts."""
        bounty_id = validation.bounty_id(bounty_id)
        base = Path(output_dir).expanduser() if output_dir else self.services.settings.data_directory / "exports"
        ensure_directory(base)
        package_root = safe_output_path(base, f"bountypilot-package-{bounty_id[:8]}")
        if package_root.exists():
            import shutil

            shutil.rmtree(package_root)
        (package_root / "evidence").mkdir(parents=True)
        (package_root / "reports").mkdir(parents=True)
        copied: list[str] = []
        evidence_rows = [e.to_dict() for e in self.services.evidence.list() if e.bounty_id == bounty_id]
        for e in evidence_rows:
            src = Path(e["content_path"])
            if src.is_file():
                dest = safe_output_path(package_root / "evidence", src.name)
                dest.write_bytes(src.read_bytes())
                copied.append(str(dest))
        for pattern_source in (self.services.settings.data_directory / "exports").glob("report-*.md"):
            dest = safe_output_path(package_root / "reports", pattern_source.name)
            dest.write_text(pattern_source.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(str(dest))
        readme = Path("README.md")
        if readme.exists():
            dest = safe_output_path(package_root, "README.md")
            dest.write_text(readme.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(str(dest))
        # Manifest with integrity hashes.
        manifest_lines = ["# Submission package manifest", ""]
        for item in sorted(package_root.rglob("*")):
            if item.is_file() and item.name != "MANIFEST.md":
                digest = hashlib.sha256(item.read_bytes()).hexdigest()
                manifest_lines.append(f"- {item.relative_to(package_root)} sha256:{digest}")
        manifest_lines += [
            "",
            "Package created by BountyPilot AI. This is NOT a submission; "
            "submit only through the official bounty process.",
        ]
        safe_output_path(package_root, "MANIFEST.md").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
        archive = safe_output_path(base, f"{package_root.name}.zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in sorted(package_root.rglob("*")):
                if item.is_file():
                    zf.write(item, item.relative_to(package_root.parent))
        return {
            "package_dir": str(package_root),
            "archive": str(archive),
            "files": copied,
            "note": "Package generated locally. BountyPilot never submits forms automatically.",
        }
