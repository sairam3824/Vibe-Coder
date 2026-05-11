"""Run orchestration service."""

from __future__ import annotations

import queue
import threading
from datetime import datetime, timezone

from apps.api.services.repository import RunRepository
from apps.api.services.run_runtime import RunRuntime
from packages.agent.graph import VibeCoderGraph
from packages.gitops.commit import CommitManager
from packages.gitops.repo_manager import RepoManager
from packages.gitops.worktree import WorkspaceManager
from packages.schemas.common import ApprovalStatus, EventType, RunStatus
from packages.schemas.run import CommitArtifact, RunSummary
from packages.schemas.task import ApproveRunRequest, TaskRequest


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunOrchestrator:
    def __init__(self, repository: RunRepository, graph: VibeCoderGraph | None = None) -> None:
        self.repository = repository
        self.graph = graph or VibeCoderGraph()
        self.workspace_manager = WorkspaceManager()
        self._queue: queue.Queue[tuple[str, TaskRequest]] = queue.Queue()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def start_run(self, run_id: str, request: TaskRequest) -> None:
        self._queue.put((run_id, request))

    def _worker_loop(self) -> None:
        while True:
            run_id, request = self._queue.get()
            try:
                self._run_sync(run_id, request)
            finally:
                self._queue.task_done()

    def _run_sync(self, run_id: str, request: TaskRequest) -> None:
        if self.repository.is_cancel_requested(run_id):
            self.repository.mark_finished(
                run_id,
                status=RunStatus.CANCELLED,
                final_summary={"success": False, "cancelled": True},
                error_message="Run cancelled before start",
            )
            self.repository.add_event(
                run_id,
                event_type=EventType.RUN_CANCELLED,
                message="Run cancelled before start",
            )
            return

        workspace_path = self.workspace_manager.prepare_workspace(request.repo_path, run_id)
        self.repository.update_workspace(run_id, workspace_path)
        self.repository.mark_running(run_id)
        runtime = RunRuntime(run_id=run_id, repository=self.repository)
        run_request = request.model_copy(update={"repo_path": workspace_path})

        try:
            final_state = self.graph.invoke(
                {
                    "run_id": run_id,
                    "request": run_request,
                    "iteration": 0,
                    "changed_files": [],
                    "validation_attempts": [],
                    "failure_signatures": [],
                    "should_retry": False,
                    "runtime": runtime,
                }
            )
            if runtime.should_cancel():
                runtime.emit(EventType.RUN_CANCELLED, "Run cancelled", step="finalize_run")
                self.repository.mark_finished(
                    run_id,
                    status=RunStatus.CANCELLED,
                    final_summary={"success": False, "cancelled": True},
                    error_message="Run cancelled",
                )
                return

            success = bool(
                final_state.get("validation_attempts")
                and final_state["validation_attempts"][-1].success
            )
            final_summary = {**final_state.get("final_summary", {}), "workspace_path": workspace_path}
            if success:
                runtime.emit(EventType.RUN_SUCCEEDED, "Run succeeded", step="finalize_run")
                self.repository.mark_finished(
                    run_id,
                    status=RunStatus.SUCCEEDED,
                    final_summary=final_summary,
                )
                artifact = CommitArtifact(
                    branch_name=request.branch_name,
                    commit_message=final_state.get("commit_message", "feat(repo): update code"),
                    commit_sha=None,
                    committed=False,
                    created_at=utc_now(),
                )
                self.repository.save_commit_artifact(run_id, artifact)
                if request.require_approval:
                    runtime.emit(
                        EventType.APPROVAL_REQUESTED,
                        "Diff approval required before commit",
                        step="finalize_run",
                    )
            else:
                runtime.emit(
                    EventType.RUN_FAILED,
                    "Run failed",
                    step="finalize_run",
                    payload={"reason": final_state.get("stop_reason")},
                )
                self.repository.mark_finished(
                    run_id,
                    status=RunStatus.FAILED,
                    final_summary=final_summary,
                    error_message=final_state.get("stop_reason"),
                )
        except Exception as exc:
            runtime.emit(
                EventType.RUN_FAILED,
                "Run crashed",
                step="orchestrator",
                payload={"error": str(exc)},
            )
            self.repository.mark_finished(
                run_id,
                status=RunStatus.FAILED,
                final_summary={"success": False, "error": str(exc)},
                error_message=str(exc),
            )
        finally:
            self.workspace_manager.cleanup_workspace(request.repo_path, workspace_path)

    def cancel_run(self, run_id: str) -> bool:
        cancelled = self.repository.mark_cancel_requested(run_id)
        if cancelled:
            self.repository.add_event(
                run_id,
                event_type=EventType.RUN_CANCEL_REQUESTED,
                message="Cancel requested",
            )
        return cancelled

    def retry_run(self, run_id: str) -> RunSummary | None:
        request = self.repository.get_task_request(run_id)
        if not request:
            return None
        summary = self.repository.create_run(request, base_run_id=run_id)
        self.start_run(summary.id, request)
        return summary

    def resume_run(self, run_id: str) -> RunSummary | None:
        return self.retry_run(run_id)

    def record_approval(self, run_id: str, request: ApproveRunRequest) -> ApprovalStatus | None:
        status = self.repository.record_approval(run_id, request)
        if status:
            self.repository.add_event(
                run_id,
                event_type=EventType.APPROVAL_RECORDED,
                message="Approval updated",
                payload={"approved": request.approved, "note": request.note},
            )
        return status

    def trigger_commit(self, run_id: str, message: str | None = None) -> CommitArtifact | None:
        detail = self.repository.get_run(run_id)
        if not detail:
            return None
        if detail.approval_status != ApprovalStatus.APPROVED:
            return None
        commit_message = message or (detail.commit_artifact.commit_message if detail.commit_artifact else None)
        commit_message = commit_message or "feat(repo): apply vibe coder changes"
        manager = CommitManager(detail.workspace_path or detail.repo_path)
        if detail.branch_name:
            RepoManager(detail.workspace_path or detail.repo_path).create_branch(detail.branch_name)
        sha = manager.commit_all(commit_message)
        artifact = CommitArtifact(
            branch_name=detail.branch_name,
            commit_message=commit_message,
            commit_sha=sha,
            committed=bool(sha),
            created_at=utc_now(),
        )
        self.repository.save_commit_artifact(run_id, artifact)
        self.repository.add_event(
            run_id,
            event_type=EventType.COMMIT_CREATED,
            message="Commit artifact created",
            payload=artifact.model_dump(),
        )
        return artifact
