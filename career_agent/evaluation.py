from __future__ import annotations

import math
from dataclasses import dataclass

from .matching import DecisionEngine
from .models import JobRecord, ResumeProfile, UserPreference


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    resume: ResumeProfile
    preference: UserPreference
    job: JobRecord
    expected_eligible: bool
    relevance: int


def build_synthetic_evaluation_set(count: int = 50) -> list[EvaluationCase]:
    if count < 1:
        raise ValueError("evaluation count must be positive")
    resume = ResumeProfile(
        name="评测候选人",
        education="本科",
        graduation_year=2028,
        location="广州",
        skills=("Python", "LangGraph", "FastAPI", "TypeScript"),
        evidence=("使用 Python、LangGraph 与 FastAPI 构建 Agent 应用", "使用 TypeScript 开发工具链"),
    )
    preference = UserPreference(("AI Agent", "大模型应用"), ("广州", "深圳", "远程"), 2028, 3)
    cases: list[EvaluationCase] = []
    for index in range(count):
        eligible = index % 4 != 0
        skills = ("Python", "LangGraph", "FastAPI") if index % 3 == 0 else ("Python", "RAG", "MCP")
        relevance = 3 if eligible and index % 3 == 0 else 2 if eligible else 0
        job = JobRecord(
            job_id=f"eval-{index:03d}",
            title="AI Agent 应用开发实习生" if eligible else "Java 后端实习生",
            company=f"评测公司{index:03d}",
            location="广州" if eligible else "北京",
            description=f"{'接受 2028 届' if eligible else '仅接受 2027 届'}，技能要求：{'、'.join(skills)}",
            skills=skills,
            required_graduation_years=(2028,) if eligible else (2027,),
            minimum_internship_months=3,
        )
        cases.append(EvaluationCase(f"case-{index:03d}", resume, preference, job, eligible, relevance))
    return cases


def _dcg(values: list[int]) -> float:
    return sum((2**value - 1) / math.log2(index + 2) for index, value in enumerate(values))


def evaluate_decisions(cases: list[EvaluationCase]) -> dict[str, float]:
    engine = DecisionEngine()
    ranked: list[tuple[float, int, bool, bool]] = []
    correct = 0
    for case in cases:
        report = engine.evaluate(case.resume, case.preference, case.job)
        correct += int(report.eligible == case.expected_eligible)
        ranked.append((report.score, case.relevance, report.eligible, case.expected_eligible))
    ranked.sort(key=lambda item: item[0], reverse=True)
    top5 = ranked[:5]
    precision_at_5 = sum(int(item[3]) for item in top5) / len(top5) if top5 else 0.0
    observed = [item[1] for item in ranked[:10]]
    ideal = sorted((case.relevance for case in cases), reverse=True)[:10]
    ideal_dcg = _dcg(ideal)
    return {
        "cases": float(len(cases)),
        "hard_filter_accuracy": correct / len(cases) if cases else 0.0,
        "precision_at_5": precision_at_5,
        "ndcg_at_10": _dcg(observed) / ideal_dcg if ideal_dcg else 0.0,
    }
