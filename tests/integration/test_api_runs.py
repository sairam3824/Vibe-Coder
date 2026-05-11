from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.db.base import Base
from apps.api.deps.services import get_orchestrator, get_run_repository
from apps.api.main import app
from apps.api.services.repository import RunRepository
from packages.schemas.run import CommitArtifact
from packages.schemas.common import ApprovalStatus


class StubOrchestrator:
    def __init__(self, repository: RunRepository) -> None:
        self.started: list[tuple[str, object]] = []
        self.repository = repository

    def start_run(self, run_id: str, request) -> None:  # noqa: ANN001
        self.started.append((run_id, request))

    def trigger_commit(self, run_id: str, message: str | None = None) -> CommitArtifact:
        return CommitArtifact(
            branch_name="codex/test",
            commit_message=message or "feat(repo): commit",
            commit_sha="abc123",
            committed=True,
            created_at=datetime.now(timezone.utc),
        )

    def record_approval(self, run_id: str, request):  # noqa: ANN001
        return self.repository.record_approval(run_id, request)


def test_run_endpoints_create_list_get_and_commit(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    repository = RunRepository(SessionLocal)
    orchestrator = StubOrchestrator(repository)
    app.dependency_overrides[get_run_repository] = lambda: repository
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator

    client = TestClient(app)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    create_response = client.post(
        "/api/runs",
        json={
            "repo_path": str(repo),
            "task": "add auth",
            "max_iterations": 2,
            "dry_run": True,
        },
    )
    assert create_response.status_code == 201
    run_id = create_response.json()["id"]

    list_response = client.get("/api/runs")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/api/runs/{run_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["task"] == "add auth"

    approval_response = client.post(f"/api/runs/{run_id}/approve", json={"approved": True})
    assert approval_response.status_code == 200

    commit_response = client.post(f"/api/runs/{run_id}/commit", json={"message": "feat(repo): add auth"})
    assert commit_response.status_code == 200
    assert commit_response.json()["committed"] is True

    app.dependency_overrides.clear()
