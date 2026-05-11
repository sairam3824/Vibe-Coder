"""Safe file editing helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from packages.gitops.diff import build_unified_diff
from packages.schemas.run import FileChange


@dataclass(slots=True)
class ProposedOperation:
    op: str
    target_snippet: str | None = None
    replacement: str | None = None
    content: str | None = None


@dataclass(slots=True)
class ProposedFileChange:
    path: str
    content: str | None
    change_type: str
    summary: str
    operations: list[ProposedOperation] = field(default_factory=list)


class FileEditor:
    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path).resolve()

    def apply_changes(self, proposed_changes: list[ProposedFileChange], iteration: int) -> list[FileChange]:
        applied: list[FileChange] = []
        for proposal in proposed_changes:
            file_path = (self.repo_path / proposal.path).resolve()
            try:
                file_path.relative_to(self.repo_path)
            except ValueError:
                raise ValueError(f"Refusing to edit path outside repository: {proposal.path}")

            before_content = file_path.read_text(encoding="utf-8") if file_path.exists() else None
            after_content = self._render_content(before_content, proposal)
            if before_content == after_content:
                continue

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(after_content, encoding="utf-8")
            diff_text = build_unified_diff(proposal.path, before_content, after_content)
            applied.append(
                FileChange(
                    path=proposal.path,
                    change_type=proposal.change_type,
                    summary=proposal.summary,
                    diff_text=diff_text,
                    before_content=before_content,
                    after_content=after_content,
                    iteration=iteration,
                )
            )
        return applied

    @staticmethod
    def _render_content(before_content: str | None, proposal: ProposedFileChange) -> str:
        if proposal.operations:
            content = before_content or ""
            for operation in proposal.operations:
                content = FileEditor._apply_operation(content, operation)
            return content
        return proposal.content or before_content or ""

    @staticmethod
    def _apply_operation(content: str, operation: ProposedOperation) -> str:
        if operation.op == "replace_snippet" and operation.target_snippet is not None:
            return content.replace(operation.target_snippet, operation.replacement or "", 1)
        if operation.op == "append":
            return content + (operation.content or "")
        if operation.op == "prepend":
            return (operation.content or "") + content
        if operation.op == "insert_after" and operation.target_snippet is not None:
            anchor = operation.target_snippet
            index = content.find(anchor)
            if index == -1:
                return content
            insert_at = index + len(anchor)
            return content[:insert_at] + (operation.content or "") + content[insert_at:]
        return content
