"""Utilities for interacting with target repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path


class RepoManager:
    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path).resolve()

    def exists(self) -> bool:
        return self.repo_path.exists()

    def is_git_repo(self) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def git_root(self) -> Path | None:
        if not self.is_git_repo():
            return None
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout.strip()
        return Path(output) if output else None

    def git_status(self) -> list[str]:
        if not self.is_git_repo():
            return []
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        return [line for line in result.stdout.splitlines() if line.strip()]

    def current_branch(self) -> str | None:
        if not self.is_git_repo():
            return None
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() or None

    def current_head(self) -> str | None:
        if not self.is_git_repo():
            return None
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() or None

    def create_branch(self, branch_name: str) -> str | None:
        if not self.is_git_repo():
            return None
        subprocess.run(
            ["git", "checkout", "-B", branch_name],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        return self.current_branch()

    def diff(self) -> str:
        if not self.is_git_repo():
            return ""
        result = subprocess.run(
            ["git", "diff", "--", "."],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout

