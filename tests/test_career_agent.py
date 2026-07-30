import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta

from career_agent.config import ProviderProfile
from career_agent.matching import DecisionEngine
from career_agent.models import JobRecord, MatchEvidence, ResumeProfile, UserPreference
from career_agent.safety import ConfirmationError, SendGuard
from career_agent.store import CareerStore


class DecisionEngineTests(unittest.TestCase):
    def setUp(self):
        self.resume = ResumeProfile(
            name="胡衍科",
            education="本科",
            graduation_year=2028,
            location="广州",
            skills=("Python", "LangGraph", "FastAPI", "TypeScript"),
            evidence=("使用 LangGraph 构建可恢复 Agent 工作流",),
        )
        self.preference = UserPreference(
            target_roles=("AI Agent", "大模型应用"),
            locations=("广州", "深圳", "远程"),
            graduation_year=2028,
            minimum_internship_months=3,
        )

    def test_hard_filter_rejects_conflicting_graduation_year(self):
        job = JobRecord(
            job_id="job-1",
            title="AI Agent 实习生",
            company="示例公司",
            location="广州",
            description="仅接受 2027 届，负责 LangGraph 应用开发",
            required_graduation_years=(2027,),
            skills=("LangGraph", "Python"),
        )

        report = DecisionEngine().evaluate(self.resume, self.preference, job)

        self.assertFalse(report.eligible)
        self.assertIn("毕业年份", report.hard_rejections[0])
        self.assertEqual(0.0, report.score)

    def test_match_report_contains_resume_and_job_evidence(self):
        job = JobRecord(
            job_id="job-2",
            title="AI Agent 应用开发实习生",
            company="示例公司",
            location="深圳",
            description="使用 Python、LangGraph 和 FastAPI 开发智能体应用",
            required_graduation_years=(2028, 2029),
            skills=("Python", "LangGraph", "FastAPI", "RAG"),
        )

        report = DecisionEngine().evaluate(self.resume, self.preference, job)

        self.assertTrue(report.eligible)
        self.assertGreater(report.score, 0)
        self.assertTrue(any(item.resume_quote for item in report.evidence))
        self.assertTrue(any(item.job_quote for item in report.evidence))
        self.assertIn("RAG", report.missing_skills)

    def test_model_judge_runs_only_after_deterministic_hard_filters(self):
        class TrackingJudge:
            def __init__(self):
                self.calls = 0

            def assess(self, resume, job):
                self.calls += 1
                return (
                    MatchEvidence("Agent", "matched", resume.evidence[0], job.description, "结构化证据"),
                )

        judge = TrackingJudge()
        engine = DecisionEngine(judge=judge)
        rejected = JobRecord(
            job_id="rejected",
            title="Agent",
            company="Acme",
            location="广州",
            description="仅接受 2027 届",
            required_graduation_years=(2027,),
        )
        accepted = JobRecord(
            job_id="accepted",
            title="AI Agent 实习生",
            company="Acme",
            location="广州",
            description="接受 2028 届，负责 Agent 应用",
            required_graduation_years=(2028,),
            skills=("Python",),
        )

        engine.evaluate(self.resume, self.preference, rejected)
        report = engine.evaluate(self.resume, self.preference, accepted)

        self.assertEqual(1, judge.calls)
        self.assertEqual("结构化证据", report.evidence[0].reason)


class ProviderProfileTests(unittest.TestCase):
    def test_api_key_is_resolved_from_environment_and_not_serialized(self):
        os.environ["CAREER_TEST_KEY"] = "secret-value"
        profile = ProviderProfile(
            name="local",
            protocol="openai_compatible",
            model="example-model",
            base_url="https://example.invalid/v1",
            api_key_env="CAREER_TEST_KEY",
        )

        self.assertEqual("secret-value", profile.resolve_api_key())
        self.assertNotIn("secret-value", profile.as_public_dict().values())


class SendGuardTests(unittest.TestCase):
    def test_confirmation_is_bound_to_target_content_and_is_idempotent(self):
        guard = SendGuard(secret=b"test-secret", ttl=timedelta(minutes=5))
        now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
        approval = guard.prepare("job-1", "你好，我想了解这个岗位。", now=now)

        first = guard.confirm(approval, "job-1", "你好，我想了解这个岗位。", now=now)
        second = guard.confirm(approval, "job-1", "你好，我想了解这个岗位。", now=now)

        self.assertEqual(first.idempotency_key, second.idempotency_key)
        with self.assertRaises(ConfirmationError):
            guard.confirm(approval, "job-2", "你好，我想了解这个岗位。", now=now)
        with self.assertRaises(ConfirmationError):
            guard.confirm(approval, "job-1", "被篡改的内容", now=now)


class CareerStoreTests(unittest.TestCase):
    def test_store_persists_jobs_reports_and_run_events(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CareerStore(os.path.join(directory, "career.sqlite3"))
            job = JobRecord(
                job_id="job-3",
                title="Agent Engineer",
                company="Acme",
                location="远程",
                description="Build reliable agents",
                skills=("Python",),
            )
            store.upsert_job(job)
            store.append_run_event("run-1", "COLLECTED", {"job_id": job.job_id})

            self.assertEqual(job, store.get_job("job-3"))
            self.assertEqual("COLLECTED", store.run_events("run-1")[0]["type"])
            store.close()

    def test_fts_search_quotes_operator_and_punctuation_input(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CareerStore(os.path.join(directory, "career.sqlite3"))
            store.upsert_job(
                JobRecord(
                    job_id="job-fts",
                    title="C++ Agent Engineer",
                    company="Acme",
                    location="广州",
                    description="Build safe tools",
                    skills=("C++",),
                )
            )
            self.assertEqual([], store.search_jobs('" OR NOT ('))
            self.assertEqual("job-fts", store.search_jobs("C++")[0].job_id)
            self.assertEqual([], store.search_jobs("   "))
            store.close()


if __name__ == "__main__":
    unittest.main()
