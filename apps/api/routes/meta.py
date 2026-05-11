"""Metadata routes for local users and projects."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.deps.services import get_run_repository
from apps.api.services.repository import RunRepository
from packages.schemas.run import ProjectProfile, UserProfile
from packages.schemas.task import ProjectRequest, UserRequest


router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/users", response_model=list[UserProfile])
def list_users(repository: RunRepository = Depends(get_run_repository)) -> list[UserProfile]:
    return repository.list_users()


@router.post("/users", response_model=UserProfile)
def create_user(
    request: UserRequest,
    repository: RunRepository = Depends(get_run_repository),
) -> UserProfile:
    return repository.create_user(request)


@router.get("/projects", response_model=list[ProjectProfile])
def list_projects(
    user_id: str | None = None,
    repository: RunRepository = Depends(get_run_repository),
) -> list[ProjectProfile]:
    return repository.list_projects(user_id=user_id)


@router.post("/projects", response_model=ProjectProfile)
def create_project(
    request: ProjectRequest,
    repository: RunRepository = Depends(get_run_repository),
) -> ProjectProfile:
    return repository.create_project(request)
