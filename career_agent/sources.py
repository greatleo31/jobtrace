from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .models import JobRecord


SKILL_TERMS = (
    "Python",
    "LangGraph",
    "LangChain",
    "FastAPI",
    "Pydantic",
    "TypeScript",
    "MCP",
    "RAG",
    "Docker",
    "MySQL",
    "Redis",
)


def _split_skills(value: Any, text: str) -> tuple[str, ...]:
    items: list[str] = []
    if isinstance(value, str):
        items.extend(re.split(r"[,，|/·\s]+", value))
    elif isinstance(value, list):
        items.extend(str(item) for item in value)
    for term in SKILL_TERMS:
        if term.casefold() in text.casefold():
            items.append(term)
    return tuple(dict.fromkeys(item.strip() for item in items if item.strip()))


def normalize_scraper_job(raw: dict[str, Any]) -> JobRecord:
    description = str(raw.get("jd") or raw.get("description") or raw.get("jobDescription") or "")
    combined = "\n".join(str(value) for value in (description, raw.get("tags"), raw.get("skills")) if value)
    years = tuple(dict.fromkeys(int(value) for value in re.findall(r"(20\d{2})\s*届", combined)))
    month_match = re.search(r"(?:至少|连续)?\s*(\d+)\s*个?月", combined)
    return JobRecord(
        job_id=str(raw.get("job_id") or raw.get("jobId") or raw.get("encryptJobId") or "").strip(),
        title=str(raw.get("title") or raw.get("jobName") or "").strip(),
        company=str(raw.get("company") or raw.get("brandName") or raw.get("boss_name") or "").strip(),
        location=str(raw.get("location") or raw.get("cityName") or "").strip(),
        description=description,
        skills=_split_skills(raw.get("skills") or raw.get("job_labels"), combined),
        required_graduation_years=years,
        minimum_internship_months=int(month_match.group(1)) if month_match else None,
        education=str(raw.get("education") or raw.get("degree") or "").strip() or None,
        salary=str(raw.get("salary") or raw.get("salaryDesc") or "").strip() or None,
        source_url=str(raw.get("job_link") or raw.get("jobUrl") or "").strip() or None,
    )


def load_scraper_jobs(path: str | Path) -> list[JobRecord]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("jobs", []) if isinstance(payload, dict) else payload
    jobs = [normalize_scraper_job(row) for row in rows if isinstance(row, dict)]
    return [job for job in jobs if job.job_id and job.title and job.company]


class BossScraperAdapter:
    """Runs the existing user-authorized scraper and returns its normalized output."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    def collect(self, keyword: str, city: str, output: str | Path, pages: int = 3) -> list[JobRecord]:
        output_path = Path(output).resolve()
        command = [
            sys.executable,
            str(self.project_root / "scripts" / "boss_cdp_raw.py"),
            "--keyword",
            keyword,
            "--city",
            city,
            "--pages",
            str(pages),
            "--output",
            str(output_path),
        ]
        subprocess.run(command, cwd=self.project_root, check=True)
        return load_scraper_jobs(output_path)
