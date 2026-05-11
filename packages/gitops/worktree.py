"""Workspace isolation helpers using git worktrees or filesystem copies."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from packages.gitops.repo_manager import RepoManager


class WorkspaceManager:
    def __init__(self, runtime_root: str | Path = "runtime/workspaces") -> None:
        self.runtime_root = Path(runtime_root)
        self.runtime_root.mkdir(parents=True, exist_ok=True)

    def prepare_workspace(self, source_repo_path: str, run_id: str) -> str:
        source = Path(source_repo_path).resolve()
        target = self.runtime_root / run_id
        if target.exists():
            return str(target)

        repo_manager = RepoManager(str(source))
        if repo_manager.is_git_repo():
            git_root = repo_manager.git_root() or source
            head = repo_manager.current_head() or "HEAD"
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(target), head],
                cwd=git_root,
                capture_output=True,
                text=True,
                check=False,
            )
            if target.exists():
                return str(target)

        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns(".git", "node_modules", ".venv", "__pycache__", "dist", "build"),
        )
        return str(target)

    def cleanup_workspace(self, source_repo_path: str, workspace_path: str) -> None:
        workspace = Path(workspace_path)
        if not workspace.exists():
            return
        source_manager = RepoManager(source_repo_path)
        if source_manager.is_git_repo():
            git_root = source_manager.git_root() or Path(source_repo_path)
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(workspace)],
                cwd=git_root,
                capture_output=True,
                text=True,
                check=False,
            )
            if not workspace.exists():
                return
        shutil.rmtree(workspace, ignore_errors=True)
