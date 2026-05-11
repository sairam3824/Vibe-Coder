"""Workflow node implementations."""

from __future__ import annotations

import json
import time
from typing import Any

from packages.agent.services.commit_message import generate_commit_message
from packages.agent.services.context_builder import ContextBuilder
from packages.agent.services.file_editor import FileEditor, ProposedFileChange, ProposedOperation
from packages.agent.services.openrouter import OpenRouterClient
from packages.agent.services.prompt_loader import PromptLoader
from packages.agent.services.repo_scanner import RepoScanner
from packages.agent.state import AgentState
from packages.sandbox.profiles import CommandProfileResolver
from packages.sandbox.runner import SandboxRunner
from packages.schemas.common import EventType
from packages.schemas.run import PlanArtifact


class WorkflowNodes:
    def __init__(
        self,
        *,
        provider: OpenRouterClient | None = None,
        repo_scanner: RepoScanner | None = None,
        context_builder: ContextBuilder | None = None,
        prompt_loader: PromptLoader | None = None,
        sandbox_runner: SandboxRunner | None = None,
        command_profile_resolver: CommandProfileResolver | None = None,
    ) -> None:
        self.provider = provider or OpenRouterClient()
        self.repo_scanner = repo_scanner or RepoScanner()
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_loader = prompt_loader or PromptLoader()
        self.sandbox_runner = sandbox_runner or SandboxRunner()
        self.command_profile_resolver = command_profile_resolver or CommandProfileResolver()

    def ingest_task(self, state: AgentState) -> AgentState:
        if self._cancelled(state, "ingest_task"):
            return state
        state["runtime"].emit(EventType.RUN_STARTED, "Run started", step="ingest_task")
        return state

    def scan_repo(self, state: AgentState) -> AgentState:
        if self._cancelled(state, "scan_repo"):
            return state
        started = time.perf_counter()
        snapshot = self.repo_scanner.scan(state["request"].repo_path)
        state["repo_snapshot"] = snapshot
        state["runtime"].save_repo_snapshot(snapshot)
        state["runtime"].emit(
            EventType.REPO_SCANNED,
            f"Scanned repository with {len(snapshot.files)} files",
            step="scan_repo",
            payload={
                "languages": snapshot.languages,
                "frameworks": snapshot.frameworks,
                "import_graph_size": len(snapshot.import_graph),
            },
        )
        state["runtime"].add_step_duration("scan_repo", time.perf_counter() - started)
        return state

    def select_relevant_files(self, state: AgentState) -> AgentState:
        if self._cancelled(state, "select_relevant_files"):
            return state
        started = time.perf_counter()
        selected = self.context_builder.select_files(state["request"].task, state["repo_snapshot"])
        snapshot = state["repo_snapshot"]
        if isinstance(self.provider, OpenRouterClient) and len(snapshot.files) > 5:
            try:
                response = self.provider.chat(
                    model=state["request"].model or "anthropic/claude-3.7-sonnet",
                    system_prompt=self.prompt_loader.load("file_selection_system"),
                    user_prompt=self.prompt_loader.load(
                        "file_selection_user",
                        task=state["request"].task,
                        languages=", ".join(snapshot.languages) or "unknown",
                        frameworks=", ".join(snapshot.frameworks) or "unknown",
                        candidate_files="\n".join(selected[:20]),
                    ),
                    json_mode=True,
                )
                state["runtime"].add_model_usage(response.usage)
                payload = self.provider.extract_json(response.content)
                model_files = [
                    item for item in payload.get("selected_files", []) if item in set(selected[:20])
                ]
                if model_files:
                    selected = model_files[:12]
            except Exception:
                pass
        state["selected_files"] = selected
        state["runtime"].emit(
            EventType.FILES_SELECTED,
            f"Selected {len(selected)} relevant files",
            step="select_relevant_files",
            payload={"files": selected},
        )
        state["runtime"].add_step_duration("select_relevant_files", time.perf_counter() - started)
        return state

    def extract_context(self, state: AgentState) -> AgentState:
        if self._cancelled(state, "extract_context"):
            return state
        started = time.perf_counter()
        context_map = self.context_builder.build_context_map(
            repo_path=state["request"].repo_path,
            selected_files=state["selected_files"],
            task=state["request"].task,
        )
        state["context_map"] = context_map
        state["runtime"].emit(
            EventType.CONTEXT_EXTRACTED,
            f"Extracted context for {len(context_map)} files",
            step="extract_context",
        )
        state["runtime"].add_step_duration("extract_context", time.perf_counter() - started)
        return state

    def plan_changes(self, state: AgentState) -> AgentState:
        if self._cancelled(state, "plan_changes"):
            return state
        started = time.perf_counter()
        snapshot = state["repo_snapshot"]
        manifest_summary = "\n\n".join(
            f"## {name}\n{content[:2000]}" for name, content in snapshot.manifests.items()
        )
        context = self._format_context(state["context_map"])
        try:
            response = self.provider.chat(
                model=state["request"].model or "anthropic/claude-3.7-sonnet",
                system_prompt=self.prompt_loader.load("planning_system"),
                user_prompt=self.prompt_loader.load(
                    "planning_user",
                    task=state["request"].task,
                    languages=", ".join(snapshot.languages) or "unknown",
                    frameworks=", ".join(snapshot.frameworks) or "unknown",
                    package_managers=", ".join(snapshot.package_managers) or "unknown",
                    git_branch=snapshot.git_branch or "detached/non-git",
                    manifest_summary=manifest_summary or "No manifests discovered.",
                    selected_files="\n".join(state["selected_files"]) or "No files selected.",
                    import_graph=json.dumps(snapshot.import_graph, indent=2)[:4000] or "{}",
                    test_targets=json.dumps(snapshot.test_targets, indent=2)[:4000] or "{}",
                    context=context or "No file context extracted.",
                ),
                json_mode=True,
            )
            state["runtime"].add_model_usage(response.usage)
            raw_plan = self.provider.extract_json(response.content)
        except Exception:
            raw_plan = {
                "goal_summary": state["request"].task,
                "assumptions": ["Model planning unavailable; generated heuristic plan."],
                "files_likely_to_change": state["selected_files"],
                "validation_strategy": ["Run the resolved command profile in Docker."],
                "rollback_risks": ["Changes may be broader than intended without full model planning."],
            }

        plan = PlanArtifact(**raw_plan, raw_response=raw_plan)
        state["plan"] = plan
        state["runtime"].save_plan(plan)
        state["runtime"].emit(
            EventType.PLAN_GENERATED,
            f"Generated plan touching {len(plan.files_likely_to_change)} files",
            step="plan_changes",
            payload=plan.model_dump(),
        )
        state["runtime"].add_step_duration("plan_changes", time.perf_counter() - started)
        return state

    def apply_changes(self, state: AgentState) -> AgentState:
        if self._cancelled(state, "apply_changes"):
            return state
        started = time.perf_counter()
        iteration = state.get("iteration", 0)
        plan_json = json.dumps(state["plan"].model_dump(), indent=2)
        context = self._format_context(state["context_map"])
        try:
            response = self.provider.chat(
                model=state["request"].model or "anthropic/claude-3.7-sonnet",
                system_prompt=self.prompt_loader.load("editing_system"),
                user_prompt=self.prompt_loader.load(
                    "editing_user",
                    task=state["request"].task,
                    plan=plan_json,
                    selected_files="\n".join(state["selected_files"]),
                    context=context,
                ),
                json_mode=True,
                timeout_seconds=180,
            )
            state["runtime"].add_model_usage(response.usage)
            payload = self.provider.extract_json(response.content)
            proposed = self._parse_changes(payload)
        except Exception as exc:
            state["stop_reason"] = f"Editing failed before changes could be applied: {exc}"
            state["should_retry"] = False
            return state

        applied = FileEditor(state["request"].repo_path).apply_changes(proposed, iteration=iteration)
        state.setdefault("changed_files", []).extend(applied)
        state["last_edit_applied"] = bool(applied)
        state["runtime"].save_file_changes(applied)
        state["runtime"].emit(
            EventType.PATCH_APPLIED,
            f"Applied {len(applied)} file changes",
            step="apply_changes",
            iteration=iteration,
            payload={"paths": [item.path for item in applied]},
        )
        if not applied:
            state["stop_reason"] = "Model returned no-op edits."
            state["should_retry"] = False
        state["runtime"].add_step_duration("apply_changes", time.perf_counter() - started)
        return state

    def run_validation(self, state: AgentState) -> AgentState:
        if self._cancelled(state, "run_validation"):
            return state
        started = time.perf_counter()
        iteration = state.get("iteration", 0)
        resolved = self.command_profile_resolver.resolve(
            state["repo_snapshot"],
            override=state["request"].command_profile,
        )
        profile = resolved.profile
        state["runtime"].emit(
            EventType.VALIDATION_STARTED,
            f"Running validation profile {profile.name}",
            step="run_validation",
            iteration=iteration,
            payload={"commands": profile.commands, "bootstrap_commands": resolved.bootstrap_commands},
        )
        attempt = self.sandbox_runner.run(
            repo_path=state["request"].repo_path,
            commands=profile.commands,
            iteration=iteration,
            profile_name=profile.name,
            languages=state["repo_snapshot"].languages,
            bootstrap_commands=resolved.bootstrap_commands,
            should_cancel=state["runtime"].should_cancel,
        )
        state.setdefault("validation_attempts", []).append(attempt)
        state["runtime"].save_validation_attempt(attempt)
        if attempt.success:
            state["runtime"].emit(
                EventType.VALIDATION_SUCCEEDED,
                "Validation succeeded",
                step="run_validation",
                iteration=iteration,
            )
            state["should_retry"] = False
        else:
            state["runtime"].emit(
                EventType.VALIDATION_FAILED,
                "Validation failed",
                step="run_validation",
                iteration=iteration,
                payload={"failure_signature": attempt.failure_signature},
            )
            state["latest_failure"] = attempt.failure_signature
            state.setdefault("failure_signatures", []).append(attempt.failure_signature or "unknown_failure")
            state["should_retry"] = True
        state["runtime"].add_step_duration("run_validation", time.perf_counter() - started)
        return state

    def analyze_failures(self, state: AgentState) -> AgentState:
        if self._cancelled(state, "analyze_failures"):
            return state
        started = time.perf_counter()
        if not state.get("should_retry"):
            state["runtime"].add_step_duration("analyze_failures", time.perf_counter() - started)
            return state
        iteration = state.get("iteration", 0)
        failures = state.get("failure_signatures", [])
        latest = failures[-1] if failures else None
        duplicate_count = failures.count(latest) if latest else 0
        if iteration + 1 >= state["request"].max_iterations:
            state["should_retry"] = False
            state["stop_reason"] = "Reached max iterations."
            return state
        if latest and duplicate_count >= 2:
            state["should_retry"] = False
            state["stop_reason"] = "Repeated identical failure pattern detected."
            return state

        diagnosis_payload: dict[str, Any] | None = None
        if isinstance(self.provider, OpenRouterClient):
            try:
                response = self.provider.chat(
                    model=state["request"].model or "anthropic/claude-3.7-sonnet",
                    system_prompt=self.prompt_loader.load("failure_diagnosis_system"),
                    user_prompt=self.prompt_loader.load(
                        "failure_diagnosis_user",
                        task=state["request"].task,
                        plan=json.dumps(state["plan"].model_dump(), indent=2),
                        changed_files="\n".join(item.path for item in state.get("changed_files", []))
                        or "No changed files.",
                        failure_output=latest or "Unknown failure.",
                    ),
                    json_mode=True,
                )
                state["runtime"].add_model_usage(response.usage)
                diagnosis_payload = self.provider.extract_json(response.content)
            except Exception:
                diagnosis_payload = None

        state["runtime"].emit(
            EventType.REPAIR_PLANNED,
            "Preparing repair iteration",
            step="analyze_failures",
            iteration=iteration,
            payload={"failure_signature": latest, "diagnosis": diagnosis_payload},
        )
        state["runtime"].add_step_duration("analyze_failures", time.perf_counter() - started)
        return state

    def repair_changes(self, state: AgentState) -> AgentState:
        if self._cancelled(state, "repair_changes"):
            return state
        started = time.perf_counter()
        if not state.get("should_retry"):
            state["runtime"].add_step_duration("repair_changes", time.perf_counter() - started)
            return state

        next_iteration = state.get("iteration", 0) + 1
        state["iteration"] = next_iteration
        state["context_map"] = self.context_builder.build_context_map(
            repo_path=state["request"].repo_path,
            selected_files=state["selected_files"],
            task=state["request"].task,
        )
        changed_summary = "\n".join(f"- {item.path}: {item.summary}" for item in state.get("changed_files", []))
        try:
            response = self.provider.chat(
                model=state["request"].model or "anthropic/claude-3.7-sonnet",
                system_prompt=self.prompt_loader.load("repair_system"),
                user_prompt=self.prompt_loader.load(
                    "repair_user",
                    task=state["request"].task,
                    plan=json.dumps(state["plan"].model_dump(), indent=2),
                    changed_files=changed_summary or "No files changed yet.",
                    failure_output=state.get("latest_failure") or "Unknown failure.",
                    context=self._format_context(state["context_map"]),
                ),
                json_mode=True,
                timeout_seconds=180,
            )
            state["runtime"].add_model_usage(response.usage)
            payload = self.provider.extract_json(response.content)
            proposed = self._parse_changes(payload)
        except Exception as exc:
            state["stop_reason"] = f"Repair generation failed: {exc}"
            state["should_retry"] = False
            return state

        applied = FileEditor(state["request"].repo_path).apply_changes(proposed, iteration=next_iteration)
        state.setdefault("changed_files", []).extend(applied)
        state["last_edit_applied"] = bool(applied)
        state["runtime"].save_file_changes(applied)
        state["runtime"].emit(
            EventType.PATCH_APPLIED,
            f"Applied {len(applied)} repair changes",
            step="repair_changes",
            iteration=next_iteration,
            payload={"paths": [item.path for item in applied]},
        )
        if not applied:
            state["should_retry"] = False
            state["stop_reason"] = "Repair iteration produced no changes."
        state["runtime"].add_step_duration("repair_changes", time.perf_counter() - started)
        return state

    def finalize_run(self, state: AgentState) -> AgentState:
        started = time.perf_counter()
        changed_files = state.get("changed_files", [])
        validation_attempts = state.get("validation_attempts", [])
        success = bool(validation_attempts and validation_attempts[-1].success)
        commit_message = generate_commit_message(state["request"].task, changed_files)
        if isinstance(self.provider, OpenRouterClient) and changed_files:
            try:
                response = self.provider.chat(
                    model=state["request"].model or "anthropic/claude-3.7-sonnet",
                    system_prompt=self.prompt_loader.load("commit_message_system"),
                    user_prompt=self.prompt_loader.load(
                        "commit_message_user",
                        task=state["request"].task,
                        plan=json.dumps(state["plan"].model_dump(), indent=2)
                        if state.get("plan")
                        else "No plan recorded.",
                        changed_files="\n".join(item.path for item in changed_files),
                    ),
                    json_mode=True,
                )
                state["runtime"].add_model_usage(response.usage)
                payload = self.provider.extract_json(response.content)
                if payload.get("commit_message"):
                    commit_message = str(payload["commit_message"])
            except Exception:
                pass
        state["commit_message"] = commit_message
        metrics = getattr(state["runtime"], "metrics", None)
        state["final_summary"] = {
            "success": success,
            "changed_files": [item.path for item in changed_files],
            "validation_attempts": len(validation_attempts),
            "stop_reason": state.get("stop_reason"),
            "commit_message": commit_message,
            "metrics": metrics.model_dump() if metrics is not None else {},
        }
        state["runtime"].add_step_duration("finalize_run", time.perf_counter() - started)
        return state

    @staticmethod
    def _format_context(context_map: dict[str, str]) -> str:
        return "\n\n".join(f"## {path}\n{content}" for path, content in context_map.items())

    @staticmethod
    def _parse_changes(payload: dict[str, Any]) -> list[ProposedFileChange]:
        return [
            ProposedFileChange(
                path=item["path"],
                content=item.get("content"),
                change_type=item.get("change_type", "update"),
                summary=item.get("summary", "Model-generated edit"),
                operations=[
                    ProposedOperation(
                        op=operation["op"],
                        target_snippet=operation.get("target_snippet"),
                        replacement=operation.get("replacement"),
                        content=operation.get("content"),
                    )
                    for operation in item.get("operations", [])
                ],
            )
            for item in payload.get("changes", [])
        ]

    @staticmethod
    def _cancelled(state: AgentState, step: str) -> bool:
        if state["runtime"].should_cancel():
            state["stop_reason"] = f"Run cancelled during {step}"
            state["should_retry"] = False
            return True
        return False
