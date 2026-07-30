from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .models import JobRecord, ResumeProfile, UserPreference
from .store import CareerStore
from .workflow import DecisionWorkflow


class JobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    title: str
    company: str
    location: str
    description: str
    skills: list[str] = Field(default_factory=list)
    required_graduation_years: list[int] = Field(default_factory=list)
    minimum_internship_months: int | None = None
    education: str | None = None
    salary: str | None = None
    source_url: str | None = None


class ResumePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    education: str
    graduation_year: int
    location: str
    skills: list[str]
    evidence: list[str]


class PreferencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_roles: list[str] = Field(min_length=1)
    locations: list[str] = Field(min_length=1)
    graduation_year: int
    minimum_internship_months: int


class MatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resume: ResumePayload
    preference: PreferencePayload
    job_ids: list[str]


def create_app(database: str | Path = "~/.jobtrace/career.sqlite3") -> FastAPI:
    app = FastAPI(title="JobTrace Career Agent", version="0.1.0")
    store = CareerStore(database)

    @app.on_event("shutdown")
    def close_store() -> None:
        store.close()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/jobs")
    def upsert_jobs(payload: list[JobPayload]) -> dict[str, int]:
        for item in payload:
            store.upsert_job(JobRecord.from_dict(item.model_dump()))
        return {"accepted": len(payload)}

    @app.get("/api/v1/jobs")
    def search_jobs(q: str = Query(min_length=1), limit: int = Query(default=20, ge=1, le=100)):
        return [job.as_dict() for job in store.search_jobs(q, limit)]

    @app.post("/api/v1/matches")
    def match_jobs(request: MatchRequest):
        jobs = [store.get_job(job_id) for job_id in request.job_ids]
        if any(job is None for job in jobs):
            raise HTTPException(status_code=404, detail="one or more jobs were not found")
        run_id = str(uuid.uuid4())
        resume = ResumeProfile(**request.resume.model_dump(exclude={"skills", "evidence"}), skills=tuple(request.resume.skills), evidence=tuple(request.resume.evidence))
        preference = UserPreference(tuple(request.preference.target_roles), tuple(request.preference.locations), request.preference.graduation_year, request.preference.minimum_internship_months)
        result = DecisionWorkflow().run(resume, preference, [job for job in jobs if job is not None])
        for event in result.events:
            store.append_run_event(run_id, event["type"], event)
        return {"run_id": run_id, "reports": [report.as_dict() for report in result.reports]}

    @app.get("/api/v1/runs/{run_id}/events")
    def run_events(run_id: str):
        return store.run_events(run_id)

    @app.get("/api/v1/runs/{run_id}/events/stream")
    def stream_events(run_id: str):
        def generate():
            for event in store.run_events(run_id):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    return app
