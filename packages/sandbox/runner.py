"""Docker-based validation runner."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Callable

from apps.api.config import get_settings
from packages.schemas.common import ValidationAttempt, ValidationCommandResult


class SandboxRunner:
    """Execute validation commands inside disposable Docker containers."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def choose_image(self, languages: list[str]) -> str:
        if {"typescript", "tsx", "javascript", "jsx"} & set(languages):
            return self.settings.sandbox_node_image
        return self.settings.sandbox_default_image

    def run(
        self,
        repo_path: str,
        commands: list[str],
        iteration: int,
        profile_name: str,
        languages: list[str],
        bootstrap_commands: list[str] | None = None,
        timeout_seconds: int | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ValidationAttempt:
        bootstrap = bootstrap_commands or []
        started_at = ValidationAttempt(
            iteration=iteration,
            profile_name=profile_name,
            commands=commands,
            bootstrap_commands=bootstrap,
            success=False,
        ).started_at
        results: list[ValidationCommandResult] = []
        timeout = timeout_seconds or self.settings.sandbox_timeout_seconds
        image = self.choose_image(languages)
        success = True

        for command in [*bootstrap, *commands]:
            if should_cancel and should_cancel():
                success = False
                results.append(
                    ValidationCommandResult(
                        command=command,
                        exit_code=130,
                        stdout="",
                        stderr="Cancelled before command execution",
                        duration_seconds=0.0,
                    )
                )
                break
            result = self._run_single(repo_path=repo_path, command=command, image=image, timeout=timeout)
            results.append(result)
            if command in bootstrap:
                continue
            if result.exit_code != 0 or result.timed_out:
                success = False
                break

        attempt = ValidationAttempt(
            iteration=iteration,
            profile_name=profile_name,
            commands=commands,
            bootstrap_commands=bootstrap,
            success=success,
            started_at=started_at,
            results=results,
        )
        attempt.failure_signature = self.summarize_failure(attempt)
        return attempt

    def _run_single(self, repo_path: str, command: str, image: str, timeout: int) -> ValidationCommandResult:
        repo = str(Path(repo_path).resolve())
        docker_command = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{repo}:/workspace",
            "-w",
            "/workspace",
            image,
            "/bin/sh",
            "-lc",
            command,
        ]
        started = time.perf_counter()
        try:
            process = subprocess.run(
                docker_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return ValidationCommandResult(
                command=command,
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_seconds=time.perf_counter() - started,
            )
        except subprocess.TimeoutExpired as exc:
            return ValidationCommandResult(
                command=command,
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                duration_seconds=time.perf_counter() - started,
                timed_out=True,
            )

    @staticmethod
    def summarize_failure(attempt: ValidationAttempt) -> str | None:
        if attempt.success:
            return None
        outputs = []
        for result in attempt.results:
            if result.exit_code == 0 and not result.timed_out:
                continue
            compact = "\n".join(
                line.strip()
                for line in (result.stderr or result.stdout).splitlines()
                if line.strip()
            )
            outputs.append(f"{result.command}:{compact[:400]}")
        return " | ".join(outputs)[:1000] if outputs else "unknown_failure"
