"""Symbol indexing utilities built on Tree-sitter extraction."""

from __future__ import annotations

from pathlib import Path

from packages.parsers.language_detection import EXTENSION_LANGUAGE_MAP
from packages.parsers.treesitter_manager import TreeSitterManager


class SymbolIndex:
    def __init__(self, tree_sitter_manager: TreeSitterManager | None = None) -> None:
        self.tree_sitter_manager = tree_sitter_manager or TreeSitterManager()

    def extract_for_files(self, root: Path, files: list[str]) -> dict[str, list[dict[str, int | str]]]:
        result: dict[str, list[dict[str, int | str]]] = {}
        for relative_path in files:
            file_path = root / relative_path
            if not file_path.is_file():
                continue
            language = EXTENSION_LANGUAGE_MAP.get(file_path.suffix.lower())
            if language not in {"python", "typescript", "tsx", "javascript", "jsx"}:
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            result[relative_path] = self.tree_sitter_manager.extract_symbols(content, language)
        return result

