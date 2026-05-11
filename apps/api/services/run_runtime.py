"""Runtime hooks used by workflow nodes to persist state and events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.api.services.repository import RunRepository
from packages.agent.services.openrouter import ModelUsage
from packages.schemas.common import EventType, RepoSnapshot, RunMetrics, ValidationAttempt
from packages.schemas.run import FileChange, PlanArtifact


@dataclass(slots=True)
class RunRuntime:
    run_id: str
    repository: RunRepository
    metrics: RunMetrics = field(default_factory=RunMetrics)

    def emit(
        self,
        event_type: EventType,
        message: str,
        *,
        payload: dict[str, Any] | None = None,
        step: str | None = None,
        iteration: int = 0,
    ) -> None:
        self.repository.add_event(
            self.run_id,
            event_type=event_type,
            message=message,
            payload=payload,
            step=step,
            iteration=iteration,
        )

    def save_repo_snapshot(self, snapshot: RepoSnapshot) -> None:
        self.repository.save_repo_snapshot(self.run_id, snapshot)

    def save_plan(self, plan: PlanArtifact) -> None:
        self.repository.save_plan(self.run_id, plan)

    def save_file_changes(self, changes: list[FileChange]) -> None:
        self.repository.save_file_changes(self.run_id, changes)

    def save_validation_attempt(self, attempt: ValidationAttempt) -> None:
        self.metrics.validation_seconds += sum(item.duration_seconds for item in attempt.results)
        self.repository.save_validation_attempt(self.run_id, attempt)
        self.repository.update_metrics(self.run_id, self.metrics)

    def add_model_usage(self, usage: ModelUsage | None) -> None:
        if not usage:
            return
        self.metrics.prompt_tokens += usage.prompt_tokens or 0
        self.metrics.completion_tokens += usage.completion_tokens or 0
        self.metrics.total_tokens += usage.total_tokens or 0
        self.metrics.model_calls += 1
        self.repository.update_metrics(self.run_id, self.metrics)

    def add_step_duration(self, step: str, seconds: float) -> None:
        self.metrics.step_durations[step] = self.metrics.step_durations.get(step, 0.0) + seconds
        self.repository.update_metrics(self.run_id, self.metrics)

    def should_cancel(self) -> bool:
        return self.repository.is_cancel_requested(self.run_id)
