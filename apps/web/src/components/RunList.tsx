import { type Run } from "../lib/api";

type RunListProps = {
  runs: Run[];
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
};

export function RunList({ runs, selectedRunId, onSelectRun }: RunListProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Runs</h2>
        <span>{runs.length}</span>
      </div>
      <div className="run-list">
        {runs.length === 0 ? <p className="muted">No runs yet.</p> : null}
        {runs.map((run) => (
          <button
            key={run.id}
            className={`run-card ${selectedRunId === run.id ? "selected" : ""}`}
            onClick={() => onSelectRun(run.id)}
            type="button"
          >
            <div className="run-card-head">
              <span className={`status-pill status-${run.status.toLowerCase()}`}>{run.status}</span>
              <span className="timestamp">{new Date(run.created_at).toLocaleString()}</span>
            </div>
            <strong>{run.task}</strong>
            <p>{run.source_repo_path}</p>
            <p className="meta-line">
              Approval: {run.approval_status}
              {run.queue_position ? ` · Queue #${run.queue_position}` : ""}
            </p>
          </button>
        ))}
      </div>
    </section>
  );
}
