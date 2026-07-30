import json
import tempfile
import unittest
from pathlib import Path

from career_agent.documents import parse_resume_text
from career_agent.evaluation import build_synthetic_evaluation_set, evaluate_decisions
from career_agent.models import ResumeProfile, UserPreference
from career_agent.sources import load_scraper_jobs
from career_agent.workflow import DecisionWorkflow


class SourceAndDocumentTests(unittest.TestCase):
    def test_scraper_output_is_normalized_to_job_records(self):
        payload = {
            "jobs": [
                {
                    "job_id": "boss-1",
                    "title": "AI Agent 实习生",
                    "boss_name": "示例科技",
                    "location": "广州·天河区",
                    "salary": "200-300元/天",
                    "skills": "Python | LangGraph",
                    "job_link": "https://example.invalid/job/1",
                    "jd": "接受 2028 届，至少实习 3 个月，使用 Python 和 LangGraph",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "boss_jobs.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            jobs = load_scraper_jobs(path)

        self.assertEqual(1, len(jobs))
        self.assertEqual((2028,), jobs[0].required_graduation_years)
        self.assertEqual(3, jobs[0].minimum_internship_months)
        self.assertIn("LangGraph", jobs[0].skills)

    def test_resume_text_parser_extracts_profile_without_inventing_fields(self):
        profile = parse_resume_text(
            """# 胡衍科\n广州｜2028届本科\n## 专业技能\nPython、LangGraph、FastAPI、TypeScript\n## 项目经历\n使用 LangGraph 构建可恢复 Agent 工作流。\n"""
        )

        self.assertEqual("胡衍科", profile.name)
        self.assertEqual(2028, profile.graduation_year)
        self.assertIn("LangGraph", profile.skills)
        self.assertNotIn("RAG", profile.skills)


class WorkflowTests(unittest.TestCase):
    def test_workflow_ranks_eligible_jobs_and_preserves_events(self):
        resume = ResumeProfile(
            name="胡衍科",
            education="本科",
            graduation_year=2028,
            location="广州",
            skills=("Python", "LangGraph", "FastAPI"),
            evidence=("使用 LangGraph 构建可恢复 Agent 工作流",),
        )
        preference = UserPreference(("AI Agent",), ("广州", "深圳"), 2028, 3)
        cases = build_synthetic_evaluation_set(count=4)
        jobs = [case.job for case in cases]

        result = DecisionWorkflow().run(resume, preference, jobs)

        self.assertEqual(len(jobs), len(result.reports))
        self.assertEqual("COMPLETED", result.events[-1]["type"])
        scores = [report.score for report in result.reports]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_evaluation_set_has_50_labeled_cases_and_metrics(self):
        cases = build_synthetic_evaluation_set(count=50)
        metrics = evaluate_decisions(cases)

        self.assertEqual(50, len(cases))
        self.assertIn("hard_filter_accuracy", metrics)
        self.assertIn("precision_at_5", metrics)
        self.assertIn("ndcg_at_10", metrics)


if __name__ == "__main__":
    unittest.main()
