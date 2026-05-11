"""Common shared schema utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class BaseSchema(BaseModel):
    """Base schema with strict-ish shared configuration."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EventType(StrEnum):
    RUN_CREATED = "RUN_CREATED"
    RUN_QUEUED = "RUN_QUEUED"
    RUN_STARTED = "RUN_STARTED"
    RUN_CANCEL_REQUESTED = "RUN_CANCEL_REQUESTED"
    RUN_CANCELLED = "RUN_CANCELLED"
    REPO_SCANNED = "REPO_SCANNED"
    FILES_SELECTED = "FILES_SELECTED"
    CONTEXT_EXTRACTED = "CONTEXT_EXTRACTED"
    PLAN_GENERATED = "PLAN_GENERATED"
    PATCH_APPLIED = "PATCH_APPLIED"
    VALIDATION_STARTED = "VALIDATION_STARTED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    VALIDATION_SUCCEEDED = "VALIDATION_SUCCEEDED"
    REPAIR_PLANNED = "REPAIR_PLANNED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_RECORDED = "APPROVAL_RECORDED"
    COMMIT_CREATED = "COMMIT_CREATED"
    RUN_FAILED = "RUN_FAILED"
    RUN_SUCCEEDED = "RUN_SUCCEEDED"
    METRICS_UPDATED = "METRICS_UPDATED"


class CommandProfile(BaseSchema):
    name: str
    commands: list[str]
    description: str | None = None


class RepoSnapshot(BaseSchema):
    repo_path: str
    is_git_repo: bool
    git_branch: str | None = None
    git_status: list[str] = Field(default_factory=list)
    manifests: dict[str, str] = Field(default_factory=dict)
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    symbols: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    import_graph: dict[str, list[str]] = Field(default_factory=dict)
    test_targets: dict[str, list[str]] = Field(default_factory=dict)


class ValidationCommandResult(BaseSchema):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


class ValidationAttempt(BaseSchema):
    iteration: int
    profile_name: str
    commands: list[str]
    bootstrap_commands: list[str] = Field(default_factory=list)
    success: bool
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)
    results: list[ValidationCommandResult] = Field(default_factory=list)
    failure_signature: str | None = None


class RunMetrics(BaseSchema):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_calls: int = 0
    step_durations: dict[str, float] = Field(default_factory=dict)
    validation_seconds: float = 0.0

