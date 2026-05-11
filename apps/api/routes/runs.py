"""Run management routes."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from apps.api.deps.services import get_orchestrator, get_run_repository
from apps.api.services.orchestrator import RunOrchestrator
from apps.api.services.repository import RunRepository
from packages.schemas.common import ApprovalStatus
from packages.schemas.run import RunDetail, RunSummary
from packages.schemas.task import ApproveRunRequest, CommitRequest, TaskRequest


router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[RunSummary])
def list_runs(
    user_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    repository: RunRepository = Depends(get_run_repository),
) -> list[RunSummary]:
    return repository.list_runs(user_id=user_id, project_id=project_id)


@router.post("", response_model=RunSummary, status_code=status.HTTP_201_CREATED)
def create_run(
    request: TaskRequest,
    repository: RunRepository = Depends(get_run_repository),
    orchestrator: RunOrchestrator = Depends(get_orchestrator),
) -> RunSummary:
    summary = repository.create_run(request)
    orchestrator.start_run(summary.id, request)
    return summary


@router.post("/{run_id}/retry", response_model=RunSummary, status_code=status.HTTP_201_CREATED)
def retry_run(
    run_id: str,
    orchestrator: RunOrchestrator = Depends(get_orchestrator),
) -> RunSummary:
    summary = orchestrator.retry_run(run_id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return summary


@router.post("/{run_id}/resume", response_model=RunSummary, status_code=status.HTTP_201_CREATED)
def resume_run(
    run_id: str,
    orchestrator: RunOrchestrator = Depends(get_orchestrator),
) -> RunSummary:
    summary = orchestrator.resume_run(run_id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return summary


@router.post("/{run_id}/cancel")
def cancel_run(
    run_id: str,
    orchestrator: RunOrchestrator = Depends(get_orchestrator),
) -> dict[str, bool]:
    if not orchestrator.cancel_run(run_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return {"ok": True}


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: str, repository: RunRepository = Depends(get_run_repository)) -> RunDetail:
    detail = repository.get_run(run_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return detail


@router.get("/{run_id}/diff")
def get_run_diff(run_id: str, repository: RunRepository = Depends(get_run_repository)) -> dict[str, object]:
    detail = repository.get_run(run_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return {
        "run_id": run_id,
        "approval_status": detail.approval_status,
        "changed_files": [item.path for item in detail.changed_files],
        "diffs": [{"path": item.path, "diff": item.diff_text} for item in detail.changed_files],
    }


@router.post("/{run_id}/approve")
def approve_run(
    run_id: str,
    request: ApproveRunRequest,
    orchestrator: RunOrchestrator = Depends(get_orchestrator),
) -> dict[str, object]:
    status_value = orchestrator.record_approval(run_id, request)
    if status_value is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return {"run_id": run_id, "approval_status": status_value}


@router.post("/{run_id}/commit")
def create_commit(
    run_id: str,
    request: CommitRequest,
    repository: RunRepository = Depends(get_run_repository),
    orchestrator: RunOrchestrator = Depends(get_orchestrator),
) -> dict[str, object]:
    detail = repository.get_run(run_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if detail.approval_status != ApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run must be approved before commit",
        )
    artifact = orchestrator.trigger_commit(run_id, request.message)
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return artifact.model_dump()


@router.get("/{run_id}/events")
async def stream_events(
    run_id: str,
    repository: RunRepository = Depends(get_run_repository),
) -> StreamingResponse:
    async def event_generator():
        last_id = 0
        while True:
            events = repository.list_events_since(run_id, after_id=last_id)
            for event in events:
                last_id = event.id or last_id
                yield f"data: {json.dumps(event.model_dump(mode='json'))}\n\n"
            detail = repository.get_run(run_id)
            if detail and detail.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                final_events = repository.list_events_since(run_id, after_id=last_id)
                for event in final_events:
                    last_id = event.id or last_id
                    yield f"data: {json.dumps(event.model_dump(mode='json'))}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

