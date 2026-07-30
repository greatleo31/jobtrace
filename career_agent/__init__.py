"""Local-first job decision agent built around user-authorized job data."""

from .matching import DecisionEngine
from .models import DecisionReport, JobRecord, ResumeProfile, UserPreference

__all__ = ["DecisionEngine", "DecisionReport", "JobRecord", "ResumeProfile", "UserPreference"]
