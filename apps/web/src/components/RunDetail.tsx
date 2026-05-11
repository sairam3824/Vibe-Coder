import { type RunWithDetails } from "../lib/api";

type RunDetailProps = {
  run: RunWithDetails | null;
  working: boolean;
  onCancel: (runId: string) => void;
  onRetry: (runId: string) => void;
  onResume: (runId: string) => void;
  onApprove: (runId: string, approved: boolean) => void;
  onCommit: (runId: string) => void;
};

export function RunDetail({
  run,
  working,
  onCancel,
  onRetry,
  onResume,
  onApprove,
  onCommit,
}: RunDetailProps) {
  if (!run) {
    return (
      <section className="panel panel-detail">
        <p className="muted">Select a run to inspect progress and artifacts.</p>
      </section>
    );
  }

  return (
    <section className="panel panel-detail">
      <div className="panel-header">
        <div>
          <h2>{run.task}</h2>
          <p className="muted">{run.source_repo_path}</p>
          <p className="meta-line">Workspace: {run.workspace_path || "pending"}</p>
        </div>
        <div className="action-column">
          <span className={`status-pill status-${run.status.toLowerCase()}`}>{run.status}</span>
          <span className="approval-pill">Approval: {run.approval_status}</span>
        </div>
      </div>

      <div className="action-row">
        <button className="secondary-button" disabled={working} onClick={() => onCancel(run.id)} type="button">
          Cancel
        </button>
        <button className="secondary-button" disabled={working} onClick={() => onRetry(run.id)} type="button">
          Retry
        </button>
        <button className="secondary-button" disabled={working} onClick={() => onResume(run.id)} type="button">
          Resume
        </button>
        <button className="secondary-button" disabled={working} onClick={() => onApprove(run.id, true)} type="button">
          Approve diff
        </button>
        <button className="secondary-button" disabled={working} onClick={() => onApprove(run.id, false)} type="button">
          Reject diff
        </button>
        <button
          className="primary-inline-button"
          disabled={working || run.approval_status !== "APPROVED"}
          onClick={() => onCommit(run.id)}
          type="button"
        >
          Commit
        </button>
      </div>

      <div className="detail-grid">
        <article className="detail-card">
          <h3>Plan</h3>
          {run.plan ? (
            <>
              <p>{run.plan.goal_summary}</p>
              <ul>
                {run.plan.files_likely_to_change.map((file) => (
                  <li key={file}>{file}</li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted">Plan not available yet.</p>
          )}
        </article>

        <article className="detail-card">
          <h3>Metrics</h3>
          <p>Model calls: {run.metrics.model_calls}</p>
          <p>Total tokens: {run.metrics.total_tokens}</p>
          <p>Validation seconds: {run.metrics.validation_seconds.toFixed(2)}</p>
          <p>Queue position: {run.queue_position ?? "none"}</p>
        </article>
      </div>

      <div className="detail-grid">
        <article className="detail-card">
          <h3>Repository</h3>
          <p>Languages: {run.repo_snapshot?.languages.join(", ") || "unknown"}</p>
          <p>Frameworks: {run.repo_snapshot?.frameworks.join(", ") || "none detected"}</p>
          <p>Git branch: {run.repo_snapshot?.git_branch || "non-git repo"}</p>
          <p>Files scanned: {run.repo_snapshot?.files.length ?? 0}</p>
        </article>

        <article className="detail-card">
          <h3>Repo analysis</h3>
          <p>Import graph entries: {Object.keys(run.repo_snapshot?.import_graph ?? {}).length}</p>
          <p>Test mappings: {Object.keys(run.repo_snapshot?.test_targets ?? {}).length}</p>
          <p>Source repo: {run.source_repo_path}</p>
        </article>
      </div>

      <article className="detail-card">
        <h3>Timeline</h3>
        <div className="timeline">
          {run.events.map((event) => (
            <div key={`${event.id}-${event.created_at}`} className="timeline-row">
              <div>
                <strong>{event.event_type}</strong>
                <p>{event.message}</p>
              </div>
              <span className="timestamp">{new Date(event.created_at).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      </article>

      <div className="detail-grid">
        <article className="detail-card">
          <h3>Changed files</h3>
          {run.changed_files.length === 0 ? <p className="muted">No file changes yet.</p> : null}
          {run.changed_files.map((change) => (
            <details key={`${change.path}-${change.iteration}`} className="change-card">
              <summary>
                <span>{change.path}</span>
                <span>
                  {change.summary}
                  {typeof change.approved === "boolean" ? ` · ${change.approved ? "approved" : "rejected"}` : ""}
                </span>
              </summary>
              <pre>{change.diff_text}</pre>
            </details>
          ))}
        </article>

        <article className="detail-card">
          <h3>Validation attempts</h3>
          {run.validation_attempts.length === 0 ? (
            <p className="muted">Validation has not started.</p>
          ) : (
            run.validation_attempts.map((attempt) => (
              <details key={`${attempt.iteration}-${attempt.profile_name}`} className="validation-card">
                <summary>
                  <span>
                    Iteration {attempt.iteration} · {attempt.profile_name}
                  </span>
                  <span>{attempt.success ? "Passed" : "Failed"}</span>
                </summary>
                {attempt.bootstrap_commands.length > 0 ? (
                  <div className="terminal-block">
                    <strong>Bootstrap</strong>
                    <pre>{attempt.bootstrap_commands.join("\n")}</pre>
                  </div>
                ) : null}
                {attempt.results.map((result) => (
                  <div key={`${attempt.iteration}-${result.command}`} className="terminal-block">
                    <strong>{result.command}</strong>
                    <pre>{result.stdout || result.stderr || "(no output)"}</pre>
                  </div>
                ))}
              </details>
            ))
          )}
        </article>
      </div>
    </section>
  );
}
