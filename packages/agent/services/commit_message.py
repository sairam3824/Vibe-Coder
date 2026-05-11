"""Commit message helpers."""

from __future__ import annotations

from packages.schemas.run import FileChange


def generate_commit_message(task: str, changed_files: list[FileChange]) -> str:
    lowered = task.lower()
    if any(keyword in lowered for keyword in ["fix", "bug", "repair"]):
        prefix = "fix"
    elif any(keyword in lowered for keyword in ["refactor", "rename", "cleanup"]):
        prefix = "refactor"
    else:
        prefix = "feat"

    scope = "repo"
    if changed_files:
        first = changed_files[0].path.split("/")[0]
        if first:
            scope = first.replace("_", "-")
    summary = task.strip().rstrip(".")
    if len(summary) > 72:
        summary = f"{summary[:69]}..."
    return f"{prefix}({scope}): {summary}"

