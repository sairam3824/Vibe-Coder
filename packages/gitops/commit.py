"""Commit helpers for target repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path


class CommitManager:
    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path)

    def commit_all(self, message: str) -> str | None:
        if not (self.repo_path / ".git").exists():
            return None
        subprocess.run(["git", "add", "."], cwd=self.repo_path, capture_output=True, text=True, check=False)
        commit = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if commit.returncode != 0:
            return None
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        return sha.stdout.strip() or None
