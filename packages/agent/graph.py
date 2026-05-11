"""LangGraph workflow assembly."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from packages.agent.nodes.workflow import WorkflowNodes
from packages.agent.state import AgentState


class VibeCoderGraph:
    def __init__(self, nodes: WorkflowNodes | None = None) -> None:
        self.nodes = nodes or WorkflowNodes()
        self.graph = self._build()

    def _build(self):
        graph = StateGraph(AgentState)
        graph.add_node("ingest_task", self.nodes.ingest_task)
        graph.add_node("scan_repo", self.nodes.scan_repo)
        graph.add_node("select_relevant_files", self.nodes.select_relevant_files)
        graph.add_node("extract_context", self.nodes.extract_context)
        graph.add_node("plan_changes", self.nodes.plan_changes)
        graph.add_node("apply_changes", self.nodes.apply_changes)
        graph.add_node("run_validation", self.nodes.run_validation)
        graph.add_node("analyze_failures", self.nodes.analyze_failures)
        graph.add_node("repair_changes", self.nodes.repair_changes)
        graph.add_node("finalize_run", self.nodes.finalize_run)

        graph.set_entry_point("ingest_task")
        graph.add_edge("ingest_task", "scan_repo")
        graph.add_edge("scan_repo", "select_relevant_files")
        graph.add_edge("select_relevant_files", "extract_context")
        graph.add_edge("extract_context", "plan_changes")
        graph.add_edge("plan_changes", "apply_changes")
        graph.add_conditional_edges(
            "apply_changes",
            lambda state: "run_validation" if state.get("last_edit_applied") else "finalize_run",
            {
                "run_validation": "run_validation",
                "finalize_run": "finalize_run",
            },
        )
        graph.add_edge("run_validation", "analyze_failures")
        graph.add_conditional_edges(
            "analyze_failures",
            lambda state: "repair_changes" if state.get("should_retry") else "finalize_run",
            {
                "repair_changes": "repair_changes",
                "finalize_run": "finalize_run",
            },
        )
        graph.add_conditional_edges(
            "repair_changes",
            lambda state: "run_validation" if state.get("last_edit_applied") else "finalize_run",
            {
                "run_validation": "run_validation",
                "finalize_run": "finalize_run",
            },
        )
        graph.add_edge("finalize_run", END)
        return graph.compile()

    def invoke(self, state: AgentState) -> AgentState:
        return self.graph.invoke(state)
