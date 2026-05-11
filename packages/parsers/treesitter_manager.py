"""Tree-sitter integration with graceful fallbacks."""

from __future__ import annotations

import re
from dataclasses import asdict
from dataclasses import dataclass
from typing import Callable

from tree_sitter import Language, Parser


@dataclass(slots=True)
class SymbolMatch:
    name: str
    kind: str
    line: int


def _language_from_callable(factory: Callable[[], object]) -> Language:
    language = factory()
    if isinstance(language, Language):
        return language
    return Language(language)


class TreeSitterManager:
    """Thin parser facade that falls back to regex if grammars are unavailable."""

    def __init__(self) -> None:
        self._languages: dict[str, Language] = {}

    def _load_language(self, language: str) -> Language | None:
        if language in self._languages:
            return self._languages[language]

        try:
            if language == "python":
                from tree_sitter_python import language as python_language

                loaded = _language_from_callable(python_language)
            elif language in {"javascript", "jsx"}:
                from tree_sitter_javascript import language as javascript_language

                loaded = _language_from_callable(javascript_language)
            elif language == "typescript":
                from tree_sitter_typescript import language_typescript

                loaded = _language_from_callable(language_typescript)
            elif language == "tsx":
                from tree_sitter_typescript import language_tsx

                loaded = _language_from_callable(language_tsx)
            else:
                return None
        except Exception:
            return None

        self._languages[language] = loaded
        return loaded

    def extract_symbols(self, content: str, language: str) -> list[dict[str, int | str]]:
        tree_sitter_language = self._load_language(language)
        if tree_sitter_language is None:
            return [asdict(item) for item in self._extract_symbols_regex(content, language)]

        try:
            parser = Parser(tree_sitter_language)
            tree = parser.parse(content.encode("utf-8"))
            root = tree.root_node
            return [asdict(item) for item in self._walk_tree(root, content.splitlines(), language)]
        except Exception:
            return [asdict(item) for item in self._extract_symbols_regex(content, language)]

    def _walk_tree(self, node, lines: list[str], language: str) -> list[SymbolMatch]:
        matches: list[SymbolMatch] = []
        interesting_types = {
            "python": {"function_definition": "function", "class_definition": "class"},
            "javascript": {
                "function_declaration": "function",
                "class_declaration": "class",
                "method_definition": "method",
            },
            "jsx": {
                "function_declaration": "function",
                "class_declaration": "class",
                "method_definition": "method",
            },
            "typescript": {
                "function_declaration": "function",
                "class_declaration": "class",
                "method_definition": "method",
                "interface_declaration": "interface",
            },
            "tsx": {
                "function_declaration": "function",
                "class_declaration": "class",
                "method_definition": "method",
                "interface_declaration": "interface",
            },
        }
        map_for_language = interesting_types.get(language, {})

        def visit(current) -> None:
            kind = map_for_language.get(current.type)
            if kind:
                name = self._node_text(current, lines)
                first_line = current.start_point[0] + 1
                match = self._extract_name_from_node_text(name, kind, language)
                matches.append(SymbolMatch(name=match, kind=kind, line=first_line))
            for child in current.children:
                visit(child)

        visit(node)
        return matches

    @staticmethod
    def _node_text(node, lines: list[str]) -> str:
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        snippet = lines[start_line : end_line + 1]
        return "\n".join(snippet)[:180]

    @staticmethod
    def _extract_name_from_node_text(text: str, kind: str, language: str) -> str:
        patterns = [
            r"(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"(?:function|class|interface)\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return f"{language}_{kind}"

    @staticmethod
    def _extract_symbols_regex(content: str, language: str) -> list[SymbolMatch]:
        patterns = {
            "python": [
                (r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)", "function"),
                (r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", "class"),
            ],
            "javascript": [
                (r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)", "function"),
                (r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", "class"),
            ],
            "jsx": [
                (r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)", "function"),
                (r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", "class"),
            ],
            "typescript": [
                (r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)", "function"),
                (r"^\s*interface\s+([A-Za-z_][A-Za-z0-9_]*)", "interface"),
                (r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", "class"),
            ],
            "tsx": [
                (r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)", "function"),
                (r"^\s*interface\s+([A-Za-z_][A-Za-z0-9_]*)", "interface"),
                (r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", "class"),
            ],
        }
        matches: list[SymbolMatch] = []
        for line_number, line in enumerate(content.splitlines(), start=1):
            for pattern, kind in patterns.get(language, []):
                match = re.search(pattern, line)
                if match:
                    matches.append(SymbolMatch(name=match.group(1), kind=kind, line=line_number))
        return matches
