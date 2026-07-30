from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class JobRecord:
    job_id: str
    title: str
    company: str
    location: str
    description: str
    skills: tuple[str, ...] = field(default_factory=tuple)
    required_graduation_years: tuple[int, ...] = field(default_factory=tuple)
    minimum_internship_months: int | None = None
    education: str | None = None
    salary: str | None = None
    source_url: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["skills"] = list(self.skills)
        data["required_graduation_years"] = list(self.required_graduation_years)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobRecord":
        value = dict(data)
        value["skills"] = tuple(value.get("skills") or ())
        value["required_graduation_years"] = tuple(value.get("required_graduation_years") or ())
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ResumeProfile:
    name: str
    education: str
    graduation_year: int
    location: str
    skills: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class UserPreference:
    target_roles: tuple[str, ...]
    locations: tuple[str, ...]
    graduation_year: int
    minimum_internship_months: int


@dataclass(frozen=True, slots=True)
class MatchEvidence:
    dimension: str
    status: str
    resume_quote: str
    job_quote: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DecisionReport:
    job_id: str
    eligible: bool
    score: float
    hard_rejections: tuple[str, ...]
    evidence: tuple[MatchEvidence, ...]
    missing_skills: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "eligible": self.eligible,
            "score": self.score,
            "hard_rejections": list(self.hard_rejections),
            "evidence": [item.as_dict() for item in self.evidence],
            "missing_skills": list(self.missing_skills),
        }
