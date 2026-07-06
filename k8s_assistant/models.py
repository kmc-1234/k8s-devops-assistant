from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Finding:
    severity: str
    title: str
    evidence: list[str]
    explanation: str
    recommended_commands: list[str]


@dataclass
class Diagnosis:
    namespace: str
    findings: list[Finding] = field(default_factory=list)
    summary: str = ""
    ai_summary: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "summary": self.summary,
            "ai_summary": self.ai_summary,
            "findings": [
                {
                    "severity": finding.severity,
                    "title": finding.title,
                    "evidence": finding.evidence,
                    "explanation": finding.explanation,
                    "recommended_commands": finding.recommended_commands,
                }
                for finding in self.findings
            ],
        }

