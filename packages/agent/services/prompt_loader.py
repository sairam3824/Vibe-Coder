"""Prompt template loading."""

from __future__ import annotations

from pathlib import Path


class PromptLoader:
    def __init__(self, base_path: str | Path | None = None) -> None:
        default_path = Path(__file__).resolve().parent.parent / "prompts" / "templates"
        self.base_path = Path(base_path or default_path)

    def load(self, name: str, **kwargs: object) -> str:
        template = (self.base_path / f"{name}.txt").read_text(encoding="utf-8")
        return template.format(**kwargs)

