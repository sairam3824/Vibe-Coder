"""Dependency providers for app services."""

from __future__ import annotations

from functools import lru_cache

from apps.api.db.session import SessionLocal
from apps.api.services.orchestrator import RunOrchestrator
from apps.api.services.repository import RunRepository


@lru_cache(maxsize=1)
def get_run_repository() -> RunRepository:
    return RunRepository(SessionLocal)


@lru_cache(maxsize=1)
def get_orchestrator() -> RunOrchestrator:
    return RunOrchestrator(repository=get_run_repository())

