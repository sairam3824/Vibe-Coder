from pathlib import Path

from packages.agent.services.repo_scanner import RepoScanner


def test_repo_scanner_detects_languages_frameworks_and_manifests(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"react":"18.0.0","vite":"5.0.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies=["fastapi","pytest"]\n',
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def hello() -> str:\n    return 'hi'\n", encoding="utf-8")
    (tmp_path / "src" / "view.tsx").write_text("export function View() { return <div/> }\n", encoding="utf-8")

    snapshot = RepoScanner().scan(str(tmp_path))

    assert "python" in snapshot.languages
    assert "tsx" in snapshot.languages
    assert "fastapi" in snapshot.frameworks
    assert "react" in snapshot.frameworks
    assert "package.json" in snapshot.manifests
    assert "src/app.py" in snapshot.files

