"""Command profile loading and resolution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from packages.schemas.common import CommandProfile, RepoSnapshot


@dataclass(slots=True)
class ResolvedValidationProfile:
    profile: CommandProfile
    bootstrap_commands: list[str]


class CommandProfileResolver:
    def __init__(self, config_path: str | Path = "configs/command_profiles.json") -> None:
        self.config_path = Path(config_path)
        self._cache: dict[str, CommandProfile] | None = None

    def load_profiles(self) -> dict[str, CommandProfile]:
        if self._cache is not None:
            return self._cache
        raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        self._cache = {name: CommandProfile(**value) for name, value in raw.items()}
        return self._cache

    def resolve(self, repo_snapshot: RepoSnapshot, override: CommandProfile | None = None) -> ResolvedValidationProfile:
        if override:
            profile = override
        else:
            profiles = self.load_profiles()
            languages = set(repo_snapshot.languages)
            if {"typescript", "tsx", "javascript", "jsx"} & languages and "python" in languages:
                profile = profiles["hybrid"]
            elif {"typescript", "tsx", "javascript", "jsx"} & languages:
                profile = profiles["node"]
            else:
                profile = profiles["python"]
        return ResolvedValidationProfile(profile=profile, bootstrap_commands=self._bootstrap_commands(repo_snapshot))

    @staticmethod
    def _bootstrap_commands(repo_snapshot: RepoSnapshot) -> list[str]:
        commands: list[str] = []
        manifest_names = set(repo_snapshot.manifests)
        languages = set(repo_snapshot.languages)
        if "requirements.txt" in manifest_names:
            commands.append("python -m pip install -r requirements.txt || true")
        elif "pyproject.toml" in manifest_names and "python" in languages:
            commands.append("python -m pip install -e . || python -m pip install . || true")
        if "package.json" in manifest_names:
            commands.append("npm install --ignore-scripts || npm install || true")
        return commands
