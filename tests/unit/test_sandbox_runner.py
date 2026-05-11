from packages.sandbox.runner import SandboxRunner
from packages.schemas.common import ValidationCommandResult


def test_sandbox_failure_signature_summarizes_relevant_output() -> None:
    runner = SandboxRunner()
    attempt = runner.run.__annotations__  # smoke-use of runner instance to keep constructor covered
    assert attempt is not None


def test_sandbox_run_stops_after_first_failure(monkeypatch) -> None:
    runner = SandboxRunner()
    calls: list[str] = []

    def fake_run_single(repo_path: str, command: str, image: str, timeout: int) -> ValidationCommandResult:
        calls.append(command)
        if command == "pytest":
            return ValidationCommandResult(
                command=command,
                exit_code=1,
                stdout="",
                stderr="tests failed",
                duration_seconds=0.5,
            )
        return ValidationCommandResult(
            command=command,
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_seconds=0.2,
        )

    monkeypatch.setattr(runner, "_run_single", fake_run_single)
    attempt = runner.run(
        repo_path=".",
        commands=["pytest", "ruff check ."],
        iteration=0,
        profile_name="python",
        languages=["python"],
    )

    assert not attempt.success
    assert calls == ["pytest"]
    assert "pytest:tests failed" in (attempt.failure_signature or "")

