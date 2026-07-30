from __future__ import annotations

import re
from typing import Protocol

from .models import DecisionReport, JobRecord, MatchEvidence, ResumeProfile, UserPreference


class EvidenceJudge(Protocol):
    def assess(self, resume: ResumeProfile, job: JobRecord) -> tuple[MatchEvidence, ...]: ...


def _contains(text: str, value: str) -> bool:
    return value.casefold() in text.casefold()


def _quote(text: str, keyword: str, radius: int = 42) -> str:
    match = re.search(re.escape(keyword), text, flags=re.IGNORECASE)
    if not match:
        return text[: radius * 2].strip()
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end].strip()


class DecisionEngine:
    """Deterministic hard filters plus evidence-based, explainable ranking."""

    def __init__(self, judge: EvidenceJudge | None = None) -> None:
        self.judge = judge

    def evaluate(
        self,
        resume: ResumeProfile,
        preference: UserPreference,
        job: JobRecord,
    ) -> DecisionReport:
        rejections: list[str] = []
        graduation_year = preference.graduation_year or resume.graduation_year
        if job.required_graduation_years and graduation_year not in job.required_graduation_years:
            years = "/".join(str(year) for year in job.required_graduation_years)
            rejections.append(f"毕业年份不匹配：岗位要求 {years} 届，候选人为 {graduation_year} 届")
        if job.minimum_internship_months and preference.minimum_internship_months < job.minimum_internship_months:
            rejections.append(
                f"实习时长不足：岗位至少 {job.minimum_internship_months} 个月，当前偏好为 {preference.minimum_internship_months} 个月"
            )
        if preference.locations and not any(_contains(job.location, location) for location in preference.locations):
            rejections.append(f"地点不匹配：{job.location}")
        if rejections:
            return DecisionReport(job.job_id, False, 0.0, tuple(rejections), (), tuple(job.skills))

        normalized_resume_skills = {skill.casefold(): skill for skill in resume.skills}
        evidence: list[MatchEvidence] = []
        missing: list[str] = []
        for skill in job.skills:
            resume_skill = normalized_resume_skills.get(skill.casefold())
            if not resume_skill:
                missing.append(skill)
                continue
            resume_quote = next(
                (item for item in resume.evidence if _contains(item, resume_skill)),
                f"技能清单：{resume_skill}",
            )
            evidence.append(
                MatchEvidence(
                    dimension=skill,
                    status="matched",
                    resume_quote=resume_quote,
                    job_quote=_quote(job.description, skill),
                    reason=f"简历与岗位均出现 {skill}",
                )
            )

        if self.judge is not None:
            judged = tuple(self.judge.assess(resume, job))
            if judged:
                evidence = list(judged)
                matched_ratio = sum(item.status == "matched" for item in evidence) / len(evidence)
                skill_score = 60.0 * matched_ratio
            else:
                skill_score = 0.0
        else:
            skill_score = 60.0 if not job.skills else 60.0 * len(evidence) / len(job.skills)
        title_score = 20.0 if any(_contains(job.title, role) for role in preference.target_roles) else 5.0
        location_score = 20.0
        return DecisionReport(
            job_id=job.job_id,
            eligible=True,
            score=round(skill_score + title_score + location_score, 2),
            hard_rejections=(),
            evidence=tuple(evidence),
            missing_skills=tuple(missing),
        )
