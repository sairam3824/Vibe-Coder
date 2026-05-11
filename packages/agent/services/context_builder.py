"""File selection and context extraction for prompts."""

from __future__ import annotations

import re
from pathlib import Path

from packages.schemas.common import RepoSnapshot


def tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(token) > 2}


class ContextBuilder:
    def select_files(self, task: str, snapshot: RepoSnapshot, limit: int = 12) -> list[str]:
        task_tokens = tokenize(task)
        scored: list[tuple[int, str]] = []
        manifests = set(snapshot.manifests)

        for file_path in snapshot.files:
            path_tokens = tokenize(file_path)
            score = len(task_tokens & path_tokens) * 5
            if Path(file_path).name in manifests:
                score += 2
            if "test" in file_path.lower():
                score += 1
            for symbol in snapshot.symbols.get(file_path, []):
                symbol_name = str(symbol.get("name", "")).lower()
                if symbol_name and any(token in symbol_name for token in task_tokens):
                    score += 4
            if score > 0:
                scored.append((score, file_path))

        if not scored:
            fallback = list(snapshot.manifests.keys()) + snapshot.files[:limit]
            return list(dict.fromkeys(fallback))[:limit]

        ordered = [path for _, path in sorted(scored, key=lambda item: (-item[0], item[1]))]
        return ordered[:limit]

    def build_context_map(
        self,
        repo_path: str,
        selected_files: list[str],
        task: str,
        max_chars_per_file: int = 4000,
    ) -> dict[str, str]:
        root = Path(repo_path)
        tokens = tokenize(task)
        context_map: dict[str, str] = {}
        for relative_path in selected_files:
            file_path = root / relative_path
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if len(content) <= max_chars_per_file:
                context_map[relative_path] = content
                continue
            lines = content.splitlines()
            relevant_lines: list[str] = []
            for index, line in enumerate(lines):
                lower = line.lower()
                if any(token in lower for token in tokens):
                    start = max(0, index - 8)
                    end = min(len(lines), index + 16)
                    relevant_lines.extend(lines[start:end])
                    if len("\n".join(relevant_lines)) >= max_chars_per_file:
                        break
            snippet = "\n".join(relevant_lines).strip() or content[:max_chars_per_file]
            context_map[relative_path] = snippet[:max_chars_per_file]
        return context_map

