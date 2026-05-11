"""Schemas for task submission."""

from __future__ import annotations

from pydantic import Field, field_validator

from packages.schemas.common import BaseSchema, CommandProfile


class TaskRequest(BaseSchema):
    repo_path: str
    task: str = Field(min_length=5)
    branch_name: str | None = None
    model: str | None = None
    max_iterations: int = Field(default=3, ge=1, le=10)
    command_profile: CommandProfile | None = None
    dry_run: bool = True
    user_id: str | None = None
    project_id: str | None = None
    require_approval: bool = True

    @field_validator("repo_path")
    @classmethod
    def validate_repo_path(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("repo_path cannot be empty")
        return value


class CommitRequest(BaseSchema):
    message: str | None = None
    create_branch_if_missing: bool = True


class ApproveRunRequest(BaseSchema):
    approved: bool
    note: str | None = None


class UserRequest(BaseSchema):
    name: str = Field(min_length=1)


class ProjectRequest(BaseSchema):
    name: str = Field(min_length=1)
    repo_path: str = Field(min_length=1)
    user_id: str | None = None

