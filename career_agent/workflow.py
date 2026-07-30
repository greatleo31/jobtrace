from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from .matching import DecisionEngine
from .models import DecisionReport, JobRecord, ResumeProfile, UserPreference


class WorkflowState(TypedDict, total=False):
    resume: ResumeProfile
    preference: UserPreference
    jobs: list[JobRecord]
    reports: list[DecisionReport]
    events: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    reports: tuple[DecisionReport, ...]
    events: tuple[dict[str, Any], ...]


class DecisionWorkflow:
    def __init__(self, engine: DecisionEngine | None = None) -> None:
        self.engine = engine or DecisionEngine()
        self._graph = self._build_graph()

    def _evaluate(self, state: WorkflowState) -> WorkflowState:
        events = list(state.get("events") or ())
        events.append({"type": "EVALUATING", "jobs": len(state["jobs"])})
        reports = [self.engine.evaluate(state["resume"], state["preference"], job) for job in state["jobs"]]
        return {"reports": reports, "events": events}

    @staticmethod
    def _rank(state: WorkflowState) -> WorkflowState:
        events = list(state.get("events") or ())
        reports = sorted(state["reports"], key=lambda item: item.score, reverse=True)
        events.append({"type": "RANKED", "eligible": sum(report.eligible for report in reports)})
        return {"reports": reports, "events": events}

    @staticmethod
    def _complete(state: WorkflowState) -> WorkflowState:
        events = list(state.get("events") or ())
        events.append({"type": "COMPLETED"})
        return {"events": events}

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return None
        builder = StateGraph(WorkflowState)
        builder.add_node("evaluate", self._evaluate)
        builder.add_node("rank", self._rank)
        builder.add_node("complete", self._complete)
        builder.add_edge(START, "evaluate")
        builder.add_edge("evaluate", "rank")
        builder.add_edge("rank", "complete")
        builder.add_edge("complete", END)
        return builder.compile()

    def run(
        self,
        resume: ResumeProfile,
        preference: UserPreference,
        jobs: list[JobRecord],
    ) -> WorkflowResult:
        initial: WorkflowState = {
            "resume": resume,
            "preference": preference,
            "jobs": jobs,
            "events": [{"type": "STARTED"}],
        }
        if self._graph is not None:
            final = self._graph.invoke(initial)
        else:
            final = dict(initial)
            final.update(self._evaluate(final))
            final.update(self._rank(final))
            final.update(self._complete(final))
        return WorkflowResult(tuple(final["reports"]), tuple(final["events"]))
