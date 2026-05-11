import { useEffect, useState } from "react";
import { type CreateRunPayload, type ProjectProfile } from "../lib/api";

type TaskFormProps = {
  onSubmit: (payload: CreateRunPayload) => Promise<void>;
  submitting: boolean;
  selectedUserId: string | null;
  selectedProject: ProjectProfile | null;
};

export function TaskForm({
  onSubmit,
  submitting,
  selectedUserId,
  selectedProject,
}: TaskFormProps) {
  const [repoPath, setRepoPath] = useState("");
  const [task, setTask] = useState("");
  const [branchName, setBranchName] = useState("codex/vibe-coder-run");
  const [model, setModel] = useState("anthropic/claude-3.7-sonnet");
  const [maxIterations, setMaxIterations] = useState(3);
  const [dryRun, setDryRun] = useState(true);
  const [requireApproval, setRequireApproval] = useState(true);
  const [commands, setCommands] = useState("pytest\nruff check .\npython -m compileall .");

  useEffect(() => {
    if (!repoPath && selectedProject?.repo_path) {
      setRepoPath(selectedProject.repo_path);
    }
  }, [selectedProject, repoPath]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({
      repo_path: repoPath,
      task,
      branch_name: branchName || undefined,
      model,
      max_iterations: maxIterations,
      dry_run: dryRun,
      user_id: selectedUserId ?? undefined,
      project_id: selectedProject?.id,
      require_approval: requireApproval,
      command_profile: {
        name: "custom",
        commands: commands
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
        description: "Custom commands from UI",
      },
    });
  }

  return (
    <form className="task-form" onSubmit={submit}>
      <label>
        <span>Repository path</span>
        <input
          value={repoPath}
          onChange={(event) => setRepoPath(event.target.value)}
          placeholder="/Users/name/projects/my-repo"
          required
        />
      </label>

      <label>
        <span>Task</span>
        <textarea
          value={task}
          onChange={(event) => setTask(event.target.value)}
          placeholder="Implement Stripe webhook handling and update the billing tests."
          rows={4}
          required
        />
      </label>

      <div className="task-grid">
        <label>
          <span>Branch</span>
          <input value={branchName} onChange={(event) => setBranchName(event.target.value)} />
        </label>

        <label>
          <span>Model</span>
          <input value={model} onChange={(event) => setModel(event.target.value)} />
        </label>

        <label>
          <span>Max iterations</span>
          <input
            type="number"
            min={1}
            max={10}
            value={maxIterations}
            onChange={(event) => setMaxIterations(Number(event.target.value))}
          />
        </label>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(event) => setDryRun(event.target.checked)}
          />
          <span>Dry run</span>
        </label>
      </div>

      <div className="task-grid">
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={requireApproval}
            onChange={(event) => setRequireApproval(event.target.checked)}
          />
          <span>Require approval</span>
        </label>
      </div>

      <label>
        <span>Validation commands</span>
        <textarea value={commands} onChange={(event) => setCommands(event.target.value)} rows={4} />
      </label>

      <button type="submit" disabled={submitting}>
        {submitting ? "Submitting..." : "Start run"}
      </button>
    </form>
  );
}
