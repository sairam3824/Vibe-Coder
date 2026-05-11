"""Schemas for persisted runs and details."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from packages.schemas.common import (
    ApprovalStatus,
    BaseSchema,
    CommandProfile,
    RepoSnapshot,
    RunMetrics,
    RunStatus,
    ValidationAttempt,
)


class UserProfile(BaseSchema):
    id: str
    name: str
    created_at: datetime


class ProjectProfile(BaseSchema):
    id: str
    name: str
    repo_path: str
    user_id: str
    created_at: datetime


class PlanArtifact(BaseSchema):
    goal_summary: str
    assumptions: list[str] = Field(default_factory=list)
    files_likely_to_change: list[str] = Field(default_factory=list)
    validation_strategy: list[str] = Field(default_factory=list)
    rollback_risks: list[str] = Field(default_factory=list)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class FileChange(BaseSchema):
    path: str
    change_type: str
    summary: str
    diff_text: str
    before_content: str | None = None
    after_content: str | None = None
    iteration: int = 0
    approved: bool | None = None


class CommitArtifact(BaseSchema):
    branch_name: str | None = None
    commit_message: str
    commit_sha: str | None = None
    committed: bool = False
    created_at: datetime


class RunSummary(BaseSchema):
    id: str
    repo_path: str
    source_repo_path: str
    workspace_path: str | None = None
    task: str
    status: RunStatus
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    branch_name: str | None = None
    model: str | None = None
    max_iterations: int
    dry_run: bool
    command_profile: CommandProfile | None = None
    user_id: str | None = None
    project_id: str | None = None
    base_run_id: str | None = None
    queue_position: int | None = None
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class RunDetail(RunSummary):
    repo_snapshot: RepoSnapshot | None = None
    plan: PlanArtifact | None = None
    changed_files: list[FileChange] = Field(default_factory=list)
    validation_attempts: list[ValidationAttempt] = Field(default_factory=list)
    events: list["AgentEvent"] = Field(default_factory=list)
    commit_artifact: CommitArtifact | None = None
    final_summary: dict[str, Any] = Field(default_factory=dict)


from packages.schemas.events import AgentEvent  # noqa: E402
