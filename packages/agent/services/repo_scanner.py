"""Repository scanning and metadata extraction."""

from __future__ import annotations

import os
import re
from pathlib import Path

from packages.gitops.repo_manager import RepoManager
from packages.parsers.language_detection import (
    detect_frameworks,
    detect_languages,
    detect_package_managers,
)
from packages.parsers.symbol_index import SymbolIndex
from packages.schemas.common import RepoSnapshot


EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
}
MANIFEST_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
}


class RepoScanner:
    def __init__(self, symbol_index: SymbolIndex | None = None) -> None:
        self.symbol_index = symbol_index or SymbolIndex()

    def scan(self, repo_path: str) -> RepoSnapshot:
        root = Path(repo_path).resolve()
        repo_manager = RepoManager(str(root))
        manifests: dict[str, str] = {}
        files: list[str] = []

        for current_root, dirnames, filenames in os.walk(root):
            dirnames[:] = [item for item in dirnames if item not in EXCLUDED_DIRS]
            for filename in filenames:
                relative = str(Path(current_root, filename).relative_to(root))
                files.append(relative)
                if filename in MANIFEST_NAMES:
                    file_path = root / relative
                    try:
                        manifests[filename] = file_path.read_text(encoding="utf-8")[:8000]
                    except UnicodeDecodeError:
                        manifests[filename] = ""

        files.sort()
        languages = detect_languages(files)
        symbols = self.symbol_index.extract_for_files(root, files[:100])
        import_graph = self._build_import_graph(root, files[:200])
        test_targets = self._build_test_targets(files)

        return RepoSnapshot(
            repo_path=str(root),
            is_git_repo=repo_manager.is_git_repo(),
            git_branch=repo_manager.current_branch(),
            git_status=repo_manager.git_status(),
            manifests=manifests,
            languages=languages,
            frameworks=detect_frameworks(manifests),
            package_managers=detect_package_managers(files),
            files=files,
            symbols=symbols,
            import_graph=import_graph,
            test_targets=test_targets,
        )

    def _build_import_graph(self, root: Path, files: list[str]) -> dict[str, list[str]]:
        graph: dict[str, list[str]] = {}
        for relative in files:
            suffix = Path(relative).suffix
            if suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            file_path = root / relative
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            imports = self._extract_imports(content, suffix)
            if imports:
                graph[relative] = imports
        return graph

    @staticmethod
    def _extract_imports(content: str, suffix: str) -> list[str]:
        if suffix == ".py":
            patterns = [r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import", r"^\s*import\s+([A-Za-z0-9_\.]+)"]
        else:
            patterns = [r"from\s+['\"]([^'\"]+)['\"]", r"import\s+['\"]([^'\"]+)['\"]"]
        matches: list[str] = []
        for line in content.splitlines():
            for pattern in patterns:
                found = re.findall(pattern, line)
                matches.extend(found)
        return sorted(set(matches))

    @staticmethod
    def _build_test_targets(files: list[str]) -> dict[str, list[str]]:
        sources = [item for item in files if "/test" not in item and "/tests" not in item]
        tests = [item for item in files if "test" in Path(item).name.lower() or "/tests/" in item]
        mapping: dict[str, list[str]] = {}
        for test_file in tests:
            stem = Path(test_file).stem.replace("test_", "").replace(".test", "").replace(".spec", "")
            linked = [source for source in sources if stem and stem in Path(source).stem]
            mapping[test_file] = linked[:10]
        return mapping
