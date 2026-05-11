import json
from pathlib import Path

from packages.agent.graph import VibeCoderGraph
from packages.agent.nodes.workflow import WorkflowNodes
from packages.agent.services.context_builder import ContextBuilder
from packages.agent.services.openrouter import ModelResponse
from packages.agent.services.prompt_loader import PromptLoader
from packages.agent.services.repo_scanner import RepoScanner
from packages.sandbox.profiles import CommandProfileResolver
from packages.schemas.common import ValidationAttempt
from packages.schemas.task import TaskRequest


class DummyRuntime:
    def __init__(self) -> None:
        self.events = []
        self.plan = None
        self.snapshot = None
        self.validation_attempts = []
        self.file_changes = []

    def emit(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.events.append((args, kwargs))

    def save_repo_snapshot(self, snapshot):
        self.snapshot = snapshot

    def save_plan(self, plan):
        self.plan = plan

    def save_file_changes(self, changes):
        self.file_changes.extend(changes)

    def save_validation_attempt(self, attempt):
        self.validation_attempts.append(attempt)

    def add_model_usage(self, usage):
        return None

    def add_step_duration(self, step, seconds):
        return None

    def should_cancel(self):
        return False


class ScriptedProvider:
    def __init__(self, responses):
        self.responses = list(responses)

    def chat(self, **kwargs):  # noqa: ANN003
        return ModelResponse(content=self.responses.pop(0), raw={})

    @staticmethod
    def extract_json(text: str):
        return json.loads(text)


class SuccessfulSandbox:
    def run(self, **kwargs):  # noqa: ANN003
        return ValidationAttempt(
            iteration=kwargs["iteration"],
            profile_name=kwargs["profile_name"],
            commands=kwargs["commands"],
            success=True,
            results=[],
        )


class FailingSandbox:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, **kwargs):  # noqa: ANN003
        self.calls += 1
        return ValidationAttempt(
            iteration=kwargs["iteration"],
            profile_name=kwargs["profile_name"],
            commands=kwargs["commands"],
            success=False,
            results=[],
            failure_signature="same_failure",
        )


def test_graph_success_path_applies_changes_and_succeeds(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("def value() -> int:\n    return 1\n", encoding="utf-8")

    provider = ScriptedProvider(
        [
            json.dumps(
                {
                    "goal_summary": "Update app.py",
                    "assumptions": [],
                    "files_likely_to_change": ["app.py"],
                    "validation_strategy": ["pytest"],
                    "rollback_risks": [],
                }
            ),
            json.dumps(
                {
                    "summary": "update value",
                    "changes": [
                        {
                            "path": "app.py",
                            "change_type": "update",
                            "summary": "Return a new integer",
                            "content": "def value() -> int:\n    return 2\n",
                        }
                    ],
                }
            ),
        ]
    )
    nodes = WorkflowNodes(
        provider=provider,  # type: ignore[arg-type]
        repo_scanner=RepoScanner(),
        context_builder=ContextBuilder(),
        prompt_loader=PromptLoader(),
        sandbox_runner=SuccessfulSandbox(),  # type: ignore[arg-type]
        command_profile_resolver=CommandProfileResolver(),
    )
    graph = VibeCoderGraph(nodes)

    state = graph.invoke(
        {
            "run_id": "run-1",
            "request": TaskRequest(repo_path=str(tmp_path), task="update value in app.py"),
            "iteration": 0,
            "changed_files": [],
            "validation_attempts": [],
            "failure_signatures": [],
            "runtime": DummyRuntime(),
        }
    )

    assert state["final_summary"]["success"] is True
    assert (tmp_path / "app.py").read_text(encoding="utf-8").strip().endswith("2")


def test_graph_stops_on_repeated_failure_signature(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("def value() -> int:\n    return 1\n", encoding="utf-8")
    provider = ScriptedProvider(
        [
            json.dumps(
                {
                    "goal_summary": "Update app.py",
                    "assumptions": [],
                    "files_likely_to_change": ["app.py"],
                    "validation_strategy": ["pytest"],
                    "rollback_risks": [],
                }
            ),
            json.dumps(
                {
                    "summary": "first edit",
                    "changes": [
                        {
                            "path": "app.py",
                            "change_type": "update",
                            "summary": "Apply first edit",
                            "content": "def value() -> int:\n    return 2\n",
                        }
                    ],
                }
            ),
            json.dumps(
                {
                    "summary": "repair edit",
                    "changes": [
                        {
                            "path": "app.py",
                            "change_type": "update",
                            "summary": "Apply repair edit",
                            "content": "def value() -> int:\n    return 3\n",
                        }
                    ],
                }
            ),
        ]
    )
    nodes = WorkflowNodes(
        provider=provider,  # type: ignore[arg-type]
        repo_scanner=RepoScanner(),
        context_builder=ContextBuilder(),
        prompt_loader=PromptLoader(),
        sandbox_runner=FailingSandbox(),  # type: ignore[arg-type]
        command_profile_resolver=CommandProfileResolver(),
    )
    graph = VibeCoderGraph(nodes)

    state = graph.invoke(
        {
            "run_id": "run-2",
            "request": TaskRequest(repo_path=str(tmp_path), task="update value in app.py"),
            "iteration": 0,
            "changed_files": [],
            "validation_attempts": [],
            "failure_signatures": [],
            "runtime": DummyRuntime(),
        }
    )

    assert state["final_summary"]["success"] is False
    assert state["stop_reason"] == "Repeated identical failure pattern detected."
    assert len(state["validation_attempts"]) == 2
