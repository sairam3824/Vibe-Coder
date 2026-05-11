"""Shared state model for the LangGraph workflow."""

from __future__ import annotations

from typing import Any, TypedDict

from packages.schemas.common import RepoSnapshot, ValidationAttempt
from packages.schemas.run import FileChange, PlanArtifact
from packages.schemas.task import TaskRequest


class AgentState(TypedDict, total=False):
    run_id: str
    request: TaskRequest
    repo_snapshot: RepoSnapshot
    selected_files: list[str]
    context_map: dict[str, str]
    plan: PlanArtifact
    changed_files: list[FileChange]
    validation_attempts: list[ValidationAttempt]
    failure_signatures: list[str]
    iteration: int
    latest_failure: str | None
    commit_message: str | None
    final_summary: dict[str, Any]
    stop_reason: str | None
    should_retry: bool
    last_edit_applied: bool
    runtime: Any
