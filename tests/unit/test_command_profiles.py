from packages.sandbox.profiles import CommandProfileResolver
from packages.schemas.common import RepoSnapshot


def test_command_profile_resolution_prefers_hybrid_for_mixed_repos() -> None:
    snapshot = RepoSnapshot(
        repo_path="/tmp/repo",
        is_git_repo=False,
        languages=["python", "typescript"],
        frameworks=[],
        package_managers=[],
        manifests={},
        files=[],
        symbols={},
    )

    resolved = CommandProfileResolver().resolve(snapshot)
    profile = resolved.profile

    assert profile.name == "hybrid"
    assert "pytest" in profile.commands[0]
