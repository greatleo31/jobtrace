from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import JobRecord


class CareerStore:
    def __init__(self, database: str | Path) -> None:
        self.path = Path(database).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS run_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_run_events_run_sequence
                ON run_events(run_id, sequence);
            CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
                job_id UNINDEXED, title, company, location, description, skills
            );
            """
        )
        self.connection.commit()

    def upsert_job(self, job: JobRecord) -> None:
        now = datetime.now(UTC).isoformat()
        payload = json.dumps(job.as_dict(), ensure_ascii=False, sort_keys=True)
        self.connection.execute(
            """
            INSERT INTO jobs(job_id, payload_json, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at
            """,
            (job.job_id, payload, now),
        )
        self.connection.execute("DELETE FROM jobs_fts WHERE job_id = ?", (job.job_id,))
        self.connection.execute(
            "INSERT INTO jobs_fts(job_id, title, company, location, description, skills) VALUES (?, ?, ?, ?, ?, ?)",
            (job.job_id, job.title, job.company, job.location, job.description, " ".join(job.skills)),
        )
        self.connection.commit()

    def get_job(self, job_id: str) -> JobRecord | None:
        row = self.connection.execute("SELECT payload_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return JobRecord.from_dict(json.loads(row["payload_json"])) if row else None

    def search_jobs(self, query: str, limit: int = 20) -> list[JobRecord]:
        normalized = query.strip()
        if not normalized:
            return []
        # Treat user input as a phrase so FTS5 operators and punctuation cannot alter the query.
        fts_query = f'"{normalized.replace(chr(34), chr(34) * 2)}"'
        rows = self.connection.execute(
            """
            SELECT j.payload_json
            FROM jobs_fts f JOIN jobs j ON j.job_id = f.job_id
            WHERE jobs_fts MATCH ?
            ORDER BY bm25(jobs_fts)
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()
        return [JobRecord.from_dict(json.loads(row["payload_json"])) for row in rows]

    def list_jobs(self, limit: int = 100) -> list[JobRecord]:
        rows = self.connection.execute(
            "SELECT payload_json FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [JobRecord.from_dict(json.loads(row["payload_json"])) for row in rows]

    def append_run_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> int:
        cursor = self.connection.execute(
            "INSERT INTO run_events(run_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (run_id, event_type, json.dumps(payload, ensure_ascii=False), datetime.now(UTC).isoformat()),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def run_events(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT sequence, event_type, payload_json, created_at FROM run_events WHERE run_id = ? ORDER BY sequence",
            (run_id,),
        ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "CareerStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
