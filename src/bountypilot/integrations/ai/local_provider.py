"""Deterministic local analysis provider.

No network, no model, no key. Produces labelled heuristic estimates by parsing
the bounty's own text: requirement sentences, deliverables, skills keywords and
explicit difficulty/effort heuristics. Untrusted content is never executed and
embedded instructions in bounty text are ignored.
"""

from __future__ import annotations

import re

from bountypilot.core.models import Analysis, Bounty
from bountypilot.integrations.ai.base import AIProvider

SKILL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Python": ("python", "django", "flask", "fastapi"),
    "TypeScript": ("typescript", "ts", "tsc"),
    "JavaScript": ("javascript", "node", "nodejs", "npm"),
    "Rust": ("rust", "anchor", "cargo"),
    "Go": ("golang", " go ", " golang "),
    "Solana": ("solana", "spl", "web3.js", "anchor program", "wallet"),
    "CLI tooling": ("cli", "command-line", "terminal", "shell"),
    "API integration": ("api", "rest", "http", "webhook"),
    "AI/LLM": ("ai", "llm", "gpt", "model", "agent", "mcp"),
    "Documentation": ("documentation", "readme", "docs", "technical writing"),
    "Content / Social": ("thread", "video", "content", "twitter", "x.com", "ugc"),
}

EFFORT_HINTS = (
    ("demo", 2.0),
    ("example", 2.0),
    ("documentation", 3.0),
    ("prototype", 6.0),
    ("integration", 8.0),
    ("automation", 8.0),
    ("workflow", 8.0),
    ("tooling", 10.0),
    ("agent", 12.0),
    ("security", 14.0),
)

_HEADING_RE = re.compile(r"(Requirements|Requirements:|What to Submit|Deliverables|How to start)", re.I)


class LocalHeuristicProvider(AIProvider):
    name = "local-heuristic"

    def is_available(self) -> bool:
        return True

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _normalize(text: str) -> str:
        """Repair glued sentences from the API text before analysis."""
        text = re.sub(r"\.(?=[A-Z])", ". ", text)  # "implementation.The" -> ". The"
        # Repair glued headings: "RequirementsThe" -> "Requirements: The"
        text = re.sub(r"\b(Requirements|Deliverables)(?=[A-Z])", r"\1: ", text)
        text = re.sub(r"\b(What to Submit|How to start|Bounty Description)(?=[A-Z])", r"\1: ", text)
        # "for:Designing" -> "for: Designing"
        text = re.sub(r":(?=[A-Z])", ": ", text)
        # Insert boundaries before well-known section headings that got glued.
        text = re.sub(
            r"(?<=[a-z0-9.!?])(What to Submit|How to start|Bounty Description|Requirements\b)",
            r"\n\1",
            text,
        )
        return text

    @classmethod
    def _sentences(cls, text: str) -> list[str]:
        text = re.sub(r"\s+", " ", cls._normalize(text or ""))
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip(" .:;") for p in parts if len(p.strip()) > 20]

    @staticmethod
    def _detect_skills(text: str) -> list[str]:
        low = f" {text.lower()} "
        found = []
        for skill, keywords in SKILL_KEYWORDS.items():
            if any(k in low for k in keywords):
                found.append(skill)
        return found

    @staticmethod
    def _difficulty(text: str) -> str:
        low = text.lower()
        score = 0
        if len(text) > 3000:
            score += 2
        elif len(text) > 1000:
            score += 1
        for kw in (
            "security",
            "blockchain",
            "transaction",
            "escrow",
            "infrastructure",
            "migration",
        ):
            if kw in low:
                score += 2
        for kw in ("documentation", "content", "thread", "demo", "example", "summary"):
            if kw in low:
                score -= 1
        if score >= 4:
            return "high (estimate)"
        if score >= 1:
            return "moderate (estimate)"
        return "low (estimate)"

    @staticmethod
    def _effort(text: str) -> float:
        low = text.lower()
        hours = 4.0
        for kw, weight in EFFORT_HINTS:
            if kw in low:
                hours += weight
        return round(min(hours, 60.0), 1)

    _HEADING_PREFIX = re.compile(
        r"^(requirements?|what to submit|deliverables|how to start|bounty description)\s*[:\-]?\s*",
        re.I,
    )

    def _extract_requirements(self, bounty: Bounty) -> list[str]:
        content = bounty.content or ""
        reqs: list[str] = []
        capture = False
        for sentence in self._sentences(content):
            stripped = self._HEADING_PREFIX.sub("", sentence)
            if re.match(r"^requirements?\b", sentence, re.I):
                capture = True
                if len(stripped) > 20:
                    reqs.append(stripped)
                continue
            if re.match(r"^(what to submit|how to start|bounty description)\b", sentence, re.I):
                capture = False
                continue
            if capture:
                reqs.append(stripped)
        if not reqs:
            reqs = [
                s for s in self._sentences(content) if re.search(r"\b(must|should|include|provide|require)\b", s, re.I)
            ]
        return reqs[:15]

    def _extract_deliverables(self, bounty: Bounty) -> list[str]:
        content = bounty.content or ""
        items: list[str] = []
        capture = False
        for sentence in self._sentences(content):
            stripped = self._HEADING_PREFIX.sub("", sentence)
            if re.match(r"^what to submit\b", sentence, re.I):
                capture = True
                if len(stripped) > 20:
                    items.append(stripped)
                continue
            if re.match(r"^how to start\b", sentence, re.I):
                capture = False
                continue
            if capture:
                items.append(stripped)
        return items[:12]

    # -- interface ------------------------------------------------------------

    def analyze(self, bounty: Bounty, focus: str = "full") -> Analysis:
        content = bounty.content or ""
        analysis = Analysis(
            bounty_id=bounty.id,
            provider=self.name,
            skills=self._detect_skills(f"{bounty.title} {content}"),
            difficulty=self._difficulty(content),
            effort_hours=self._effort(content),
        )
        reqs = self._extract_requirements(bounty)
        deliverables = self._extract_deliverables(bounty)
        analysis.requirements = reqs
        analysis.deliverables = deliverables
        analysis.acceptance_criteria = [
            "Each listed requirement has a matching implementation or artifact"
            " (verify manually; these are heuristic extractions)."
        ]
        analysis.unknowns = [
            "Exact reviewer expectations are not published; confirm in the bounty channel.",
            "Effort and difficulty are heuristic estimates derived from bounty text, not guarantees.",
        ]
        if focus == "skills":
            analysis.requirements = []
            analysis.deliverables = []
        elif focus == "difficulty":
            analysis.requirements = []
            analysis.deliverables = []
        elif focus == "effort":
            analysis.requirements = []
            analysis.deliverables = []
        elif focus == "requirements":
            analysis.skills = []
            analysis.difficulty = "unknown"
            analysis.effort_hours = None
        analysis.summary = (
            f"Heuristic analysis of '{bounty.title}': {len(reqs)} requirement sentence(s), "
            f"{len(deliverables)} deliverable sentence(s), difficulty {analysis.difficulty}, "
            f"~{analysis.effort_hours}h effort (estimate)."
        )
        return analysis
