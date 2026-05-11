"""Language and framework detection helpers."""

from __future__ import annotations

from collections import Counter
from pathlib import Path


EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".json": "json",
    ".toml": "toml",
}


def detect_languages(files: list[str]) -> list[str]:
    counter: Counter[str] = Counter()
    for file_path in files:
        suffix = Path(file_path).suffix.lower()
        language = EXTENSION_LANGUAGE_MAP.get(suffix)
        if language:
            counter[language] += 1
    return [language for language, _ in counter.most_common()]


def detect_package_managers(files: list[str]) -> list[str]:
    managers: list[str] = []
    known = {
        "package-lock.json": "npm",
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "poetry.lock": "poetry",
        "requirements.txt": "pip",
        "uv.lock": "uv",
    }
    names = {Path(item).name for item in files}
    for file_name, manager in known.items():
        if file_name in names:
            managers.append(manager)
    return managers


def detect_frameworks(manifests: dict[str, str]) -> list[str]:
    frameworks: list[str] = []
    package_json = manifests.get("package.json", "")
    pyproject = manifests.get("pyproject.toml", "")

    if "next" in package_json:
        frameworks.append("nextjs")
    if "react" in package_json:
        frameworks.append("react")
    if "vite" in package_json:
        frameworks.append("vite")
    if "fastapi" in pyproject or "fastapi" in manifests.get("requirements.txt", ""):
        frameworks.append("fastapi")
    if "pytest" in pyproject or "pytest" in manifests.get("requirements.txt", ""):
        frameworks.append("pytest")
    return frameworks

