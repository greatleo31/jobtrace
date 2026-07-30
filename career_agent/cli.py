from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_provider_profiles
from .documents import extract_resume_text, parse_resume_text
from .evaluation import build_synthetic_evaluation_set, evaluate_decisions
from .models import UserPreference
from .sources import load_scraper_jobs
from .store import CareerStore
from .workflow import DecisionWorkflow


DEFAULT_DATABASE = "~/.jobtrace/career.sqlite3"
DEFAULT_CONFIG = "~/.jobtrace/config.toml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobtrace-agent")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--config", default=DEFAULT_CONFIG)
    importer = commands.add_parser("import")
    importer.add_argument("file")
    matcher = commands.add_parser("match")
    matcher.add_argument("--resume", required=True)
    matcher.add_argument("--jobs", required=True)
    matcher.add_argument("--roles", default="AI Agent,大模型应用")
    matcher.add_argument("--locations", default="广州,深圳,远程")
    matcher.add_argument("--graduation-year", type=int, required=True)
    matcher.add_argument("--months", type=int, default=3)
    commands.add_parser("evaluate")
    commands.add_parser("tui")
    server = commands.add_parser("serve")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8765)
    return parser


def _emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    database = Path(args.database).expanduser()
    if args.command == "doctor":
        profiles = load_provider_profiles(args.config)
        _emit({"ok": True, "database": str(database), "providers": [profile.as_public_dict() for profile in profiles.values()]})
        return 0
    if args.command == "evaluate":
        _emit(evaluate_decisions(build_synthetic_evaluation_set(50)))
        return 0
    if args.command == "tui":
        from .tui import run_tui

        run_tui(database)
        return 0
    if args.command == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(database), host=args.host, port=args.port)
        return 0
    if args.command == "import":
        jobs = load_scraper_jobs(args.file)
        with CareerStore(database) as store:
            for job in jobs:
                store.upsert_job(job)
        _emit({"ok": True, "imported": len(jobs)})
        return 0
    if args.command == "match":
        resume = parse_resume_text(extract_resume_text(args.resume))
        jobs = load_scraper_jobs(args.jobs)
        preference = UserPreference(
            tuple(item.strip() for item in args.roles.split(",") if item.strip()),
            tuple(item.strip() for item in args.locations.split(",") if item.strip()),
            args.graduation_year,
            args.months,
        )
        result = DecisionWorkflow().run(resume, preference, jobs)
        _emit({"reports": [report.as_dict() for report in result.reports], "events": result.events})
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
