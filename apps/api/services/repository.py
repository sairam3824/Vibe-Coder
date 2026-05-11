"""Persistence and query helpers for runs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from apps.api.models import (
    ApprovalRecord,
    CommitArtifactRecord,
    EventRecord,
    FileChangeRecord,
    PlanRecord,
    ProjectRecord,
    RunRecord,
    UserRecord,
    ValidationAttemptRecord,
)
from packages.schemas.common import (
    ApprovalStatus,
    EventType,
    RepoSnapshot,
    RunMetrics,
    RunStatus,
    ValidationAttempt,
)
from packages.schemas.events import AgentEvent
from packages.schemas.run import (
    CommitArtifact,
    FileChange,
    PlanArtifact,
    ProjectProfile,
    RunDetail,
    RunSummary,
    UserProfile,
)
from packages.schemas.task import ApproveRunRequest, ProjectRequest, TaskRequest, UserRequest


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_USER_ID = "local-user"
DEFAULT_PROJECT_ID = "default-project"


class RunRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory
        self.ensure_default_entities()

    def ensure_default_entities(self) -> None:
        with self.session_factory() as session:
            user = session.get(UserRecord, DEFAULT_USER_ID)
            if not user:
                session.add(UserRecord(id=DEFAULT_USER_ID, name="Local User"))
            project = session.get(ProjectRecord, DEFAULT_PROJECT_ID)
            if not project:
                session.add(
                    ProjectRecord(
                        id=DEFAULT_PROJECT_ID,
                        name="Default Project",
                        repo_path="",
                        user_id=DEFAULT_USER_ID,
                    )
                )
            session.commit()

    def list_users(self) -> list[UserProfile]:
        with self.session_factory() as session:
            users = session.scalars(select(UserRecord).order_by(UserRecord.created_at.asc())).all()
            return [UserProfile(id=item.id, name=item.name, created_at=item.created_at) for item in users]

    def create_user(self, request: UserRequest) -> UserProfile:
        user = UserRecord(id=str(uuid.uuid4()), name=request.name)
        with self.session_factory() as session:
            session.add(user)
            session.commit()
            return UserProfile(id=user.id, name=user.name, created_at=user.created_at)

    def list_projects(self, user_id: str | None = None) -> list[ProjectProfile]:
        with self.session_factory() as session:
            statement = select(ProjectRecord).order_by(ProjectRecord.created_at.asc())
            if user_id:
                statement = statement.where(ProjectRecord.user_id == user_id)
            projects = session.scalars(statement).all()
            return [
                ProjectProfile(
                    id=item.id,
                    name=item.name,
                    repo_path=item.repo_path,
                    user_id=item.user_id,
                    created_at=item.created_at,
                )
                for item in projects
            ]

    def create_project(self, request: ProjectRequest) -> ProjectProfile:
        project = ProjectRecord(
            id=str(uuid.uuid4()),
            name=request.name,
            repo_path=request.repo_path,
            user_id=request.user_id or DEFAULT_USER_ID,
        )
        with self.session_factory() as session:
            session.add(project)
            session.commit()
            return ProjectProfile(
                id=project.id,
                name=project.name,
                repo_path=project.repo_path,
                user_id=project.user_id,
                created_at=project.created_at,
            )

    def create_run(self, request: TaskRequest, *, base_run_id: str | None = None) -> RunSummary:
        run_id = str(uuid.uuid4())
        user_id = request.user_id or DEFAULT_USER_ID
        project_id = request.project_id or DEFAULT_PROJECT_ID
        with self.session_factory() as session:
            record = RunRecord(
                id=run_id,
                repo_path=request.repo_path,
                source_repo_path=request.repo_path,
                workspace_path=None,
                task=request.task,
                status=RunStatus.QUEUED,
                approval_status=ApprovalStatus.PENDING if request.require_approval else ApprovalStatus.APPROVED,
                branch_name=request.branch_name,
                model=request.model,
                max_iterations=request.max_iterations,
                dry_run=request.dry_run,
                user_id=user_id,
                project_id=project_id,
                base_run_id=base_run_id,
                command_profile_json=request.command_profile.model_dump_json()
                if request.command_profile
                else None,
                request_json=request.model_dump_json(),
                metrics_json=RunMetrics().model_dump_json(),
            )
            session.add(record)
            session.add(
                EventRecord(
                    run_id=run_id,
                    event_type=EventType.RUN_CREATED,
                    message="Run created",
                    payload_json=json.dumps({"task": request.task}),
                )
            )
            session.add(
                EventRecord(
                    run_id=run_id,
                    event_type=EventType.RUN_QUEUED,
                    message="Run queued",
                    payload_json=json.dumps({}),
                )
            )
            session.commit()
            session.refresh(record)
            return self._to_summary(session, record)

    def list_runs(
        self,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[RunSummary]:
        with self.session_factory() as session:
            statement = select(RunRecord).order_by(RunRecord.created_at.desc())
            if user_id:
                statement = statement.where(RunRecord.user_id == user_id)
            if project_id:
                statement = statement.where(RunRecord.project_id == project_id)
            records = session.scalars(statement).all()
            return [self._to_summary(session, record) for record in records]

    def get_run(self, run_id: str) -> RunDetail | None:
        with self.session_factory() as session:
            statement = (
                select(RunRecord)
                .where(RunRecord.id == run_id)
                .options(
                    selectinload(RunRecord.events),
                    selectinload(RunRecord.plans),
                    selectinload(RunRecord.file_changes),
                    selectinload(RunRecord.validation_attempts),
                    selectinload(RunRecord.commit_artifacts),
                    selectinload(RunRecord.approvals),
                )
            )
            record = session.scalars(statement).first()
            if not record:
                return None
            return self._to_detail(session, record)

    def get_task_request(self, run_id: str) -> TaskRequest | None:
        with self.session_factory() as session:
            record = session.get(RunRecord, run_id)
            if not record or not record.request_json:
                return None
            return TaskRequest.model_validate_json(record.request_json)

    def update_workspace(self, run_id: str, workspace_path: str) -> None:
        with self.session_factory() as session:
            record = session.get(RunRecord, run_id)
            if not record:
                return
            record.workspace_path = workspace_path
            record.repo_path = workspace_path
            record.updated_at = utcnow()
            session.commit()

    def mark_running(self, run_id: str) -> None:
        with self.session_factory() as session:
            record = session.get(RunRecord, run_id)
            if not record:
                return
            record.status = RunStatus.RUNNING
            record.started_at = utcnow()
            record.updated_at = utcnow()
            session.commit()

    def mark_cancel_requested(self, run_id: str) -> bool:
        with self.session_factory() as session:
            record = session.get(RunRecord, run_id)
            if not record:
                return False
            record.cancel_requested = True
            record.updated_at = utcnow()
            if record.status == RunStatus.QUEUED:
                record.status = RunStatus.CANCELLED
                record.completed_at = utcnow()
            session.commit()
            return True

    def is_cancel_requested(self, run_id: str) -> bool:
        with self.session_factory() as session:
            record = session.get(RunRecord, run_id)
            return bool(record.cancel_requested) if record else False

    def mark_finished(
        self,
        run_id: str,
        *,
        status: RunStatus,
        final_summary: dict[str, Any],
        error_message: str | None = None,
    ) -> None:
        with self.session_factory() as session:
            record = session.get(RunRecord, run_id)
            if not record:
                return
            record.status = status
            record.final_summary_json = json.dumps(final_summary)
            record.error_message = error_message
            record.completed_at = utcnow()
            record.updated_at = utcnow()
            session.commit()

    def update_metrics(self, run_id: str, metrics: RunMetrics) -> None:
        with self.session_factory() as session:
            record = session.get(RunRecord, run_id)
            if not record:
                return
            record.metrics_json = metrics.model_dump_json()
            record.updated_at = utcnow()
            session.commit()

    def save_repo_snapshot(self, run_id: str, snapshot: RepoSnapshot) -> None:
        with self.session_factory() as session:
            record = session.get(RunRecord, run_id)
            if not record:
                return
            record.repo_snapshot_json = snapshot.model_dump_json()
            record.updated_at = utcnow()
            session.commit()

    def save_plan(self, run_id: str, plan: PlanArtifact) -> None:
        with self.session_factory() as session:
            session.add(
                PlanRecord(
                    run_id=run_id,
                    goal_summary=plan.goal_summary,
                    assumptions_json=json.dumps(plan.assumptions),
                    files_json=json.dumps(plan.files_likely_to_change),
                    validation_strategy_json=json.dumps(plan.validation_strategy),
                    rollback_risks_json=json.dumps(plan.rollback_risks),
                    raw_plan_json=json.dumps(plan.raw_response),
                )
            )
            session.commit()

    def add_event(
        self,
        run_id: str,
        *,
        event_type: EventType,
        message: str,
        payload: dict[str, Any] | None = None,
        step: str | None = None,
        iteration: int = 0,
    ) -> None:
        with self.session_factory() as session:
            session.add(
                EventRecord(
                    run_id=run_id,
                    event_type=event_type,
                    message=message,
                    payload_json=json.dumps(payload or {}),
                    step=step,
                    iteration=iteration,
                )
            )
            session.commit()

    def save_file_changes(self, run_id: str, changes: list[FileChange]) -> None:
        if not changes:
            return
        with self.session_factory() as session:
            session.add_all(
                [
                    FileChangeRecord(
                        run_id=run_id,
                        path=change.path,
                        change_type=change.change_type,
                        summary=change.summary,
                        diff_text=change.diff_text,
                        before_content=change.before_content,
                        after_content=change.after_content,
                        approved=change.approved,
                        iteration=change.iteration,
                    )
                    for change in changes
                ]
            )
            session.commit()

    def save_validation_attempt(self, run_id: str, attempt: ValidationAttempt) -> None:
        with self.session_factory() as session:
            session.add(
                ValidationAttemptRecord(
                    run_id=run_id,
                    iteration=attempt.iteration,
                    profile_name=attempt.profile_name,
                    commands_json=json.dumps(attempt.commands),
                    success=attempt.success,
                    results_json=attempt.model_dump_json(),
                    failure_signature=attempt.failure_signature,
                    started_at=attempt.started_at,
                    completed_at=attempt.completed_at,
                )
            )
            session.commit()

    def save_commit_artifact(self, run_id: str, artifact: CommitArtifact) -> None:
        with self.session_factory() as session:
            session.add(
                CommitArtifactRecord(
                    run_id=run_id,
                    branch_name=artifact.branch_name,
                    commit_message=artifact.commit_message,
                    commit_sha=artifact.commit_sha,
                    committed=artifact.committed,
                    created_at=artifact.created_at,
                )
            )
            session.commit()

    def record_approval(self, run_id: str, request: ApproveRunRequest) -> ApprovalStatus | None:
        with self.session_factory() as session:
            record = session.get(RunRecord, run_id)
            if not record:
                return None
            session.add(
                ApprovalRecord(
                    run_id=run_id,
                    approved=request.approved,
                    note=request.note,
                )
            )
            record.approval_status = (
                ApprovalStatus.APPROVED if request.approved else ApprovalStatus.REJECTED
            )
            for item in record.file_changes:
                item.approved = request.approved
            record.updated_at = utcnow()
            session.commit()
            return ApprovalStatus(record.approval_status)

    def list_events_since(self, run_id: str, after_id: int = 0) -> list[AgentEvent]:
        with self.session_factory() as session:
            events = session.scalars(
                select(EventRecord)
                .where(EventRecord.run_id == run_id, EventRecord.id > after_id)
                .order_by(EventRecord.id.asc())
            ).all()
            return [self._to_event(item) for item in events]

    def _queue_position(self, session: Session, run_id: str) -> int | None:
        queued_ids = session.scalars(
            select(RunRecord.id)
            .where(RunRecord.status == RunStatus.QUEUED)
            .order_by(RunRecord.created_at.asc())
        ).all()
        try:
            return queued_ids.index(run_id) + 1
        except ValueError:
            return None

    def _to_summary(self, session: Session, record: RunRecord) -> RunSummary:
        command_profile = json.loads(record.command_profile_json) if record.command_profile_json else None
        metrics = RunMetrics.model_validate_json(record.metrics_json) if record.metrics_json else RunMetrics()
        return RunSummary(
            id=record.id,
            repo_path=record.repo_path,
            source_repo_path=record.source_repo_path,
            workspace_path=record.workspace_path,
            task=record.task,
            status=RunStatus(record.status),
            approval_status=ApprovalStatus(record.approval_status),
            branch_name=record.branch_name,
            model=record.model,
            max_iterations=record.max_iterations,
            dry_run=record.dry_run,
            command_profile=command_profile,
            user_id=record.user_id,
            project_id=record.project_id,
            base_run_id=record.base_run_id,
            queue_position=self._queue_position(session, record.id),
            metrics=metrics,
            created_at=record.created_at,
            updated_at=record.updated_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
            error_message=record.error_message,
        )

    def _to_detail(self, session: Session, record: RunRecord) -> RunDetail:
        plan_record = record.plans[-1] if record.plans else None
        commit_record = record.commit_artifacts[-1] if record.commit_artifacts else None
        return RunDetail(
            **self._to_summary(session, record).model_dump(),
            repo_snapshot=RepoSnapshot.model_validate_json(record.repo_snapshot_json)
            if record.repo_snapshot_json
            else None,
            plan=self._to_plan(plan_record) if plan_record else None,
            changed_files=[self._to_file_change(item) for item in record.file_changes],
            validation_attempts=[self._to_validation(item) for item in record.validation_attempts],
            events=[self._to_event(item) for item in record.events],
            commit_artifact=self._to_commit(commit_record) if commit_record else None,
            final_summary=json.loads(record.final_summary_json) if record.final_summary_json else {},
        )

    @staticmethod
    def _to_plan(record: PlanRecord) -> PlanArtifact:
        return PlanArtifact(
            goal_summary=record.goal_summary,
            assumptions=json.loads(record.assumptions_json),
            files_likely_to_change=json.loads(record.files_json),
            validation_strategy=json.loads(record.validation_strategy_json),
            rollback_risks=json.loads(record.rollback_risks_json),
            raw_response=json.loads(record.raw_plan_json),
        )

    @staticmethod
    def _to_file_change(record: FileChangeRecord) -> FileChange:
        return FileChange(
            path=record.path,
            change_type=record.change_type,
            summary=record.summary,
            diff_text=record.diff_text,
            before_content=record.before_content,
            after_content=record.after_content,
            approved=record.approved,
            iteration=record.iteration,
        )

    @staticmethod
    def _to_validation(record: ValidationAttemptRecord) -> ValidationAttempt:
        payload = json.loads(record.results_json)
        return ValidationAttempt(**payload)

    @staticmethod
    def _to_event(record: EventRecord) -> AgentEvent:
        return AgentEvent(
            id=record.id,
            run_id=record.run_id,
            event_type=record.event_type,
            message=record.message,
            payload=json.loads(record.payload_json),
            step=record.step,
            iteration=record.iteration,
            created_at=record.created_at,
        )

    @staticmethod
    def _to_commit(record: CommitArtifactRecord) -> CommitArtifact:
        return CommitArtifact(
            branch_name=record.branch_name,
            commit_message=record.commit_message,
            commit_sha=record.commit_sha,
            committed=record.committed,
            created_at=record.created_at,
        )
