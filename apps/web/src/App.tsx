import { useEffect, useState } from "react";
import { RunDetail } from "./components/RunDetail";
import { RunList } from "./components/RunList";
import { TaskForm } from "./components/TaskForm";
import {
  approveRun,
  cancelRun,
  createCommit,
  createProject,
  createRun,
  createUser,
  fetchProjects,
  fetchRun,
  fetchRuns,
  fetchUsers,
  retryRun,
  resumeRun,
  subscribeToRunEvents,
  type CreateRunPayload,
  type ProjectProfile,
  type Run,
  type RunWithDetails,
  type UserProfile,
} from "./lib/api";

const USER_STORAGE_KEY = "vibe-coder-user-id";
const PROJECT_STORAGE_KEY = "vibe-coder-project-id";

export function App() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [projects, setProjects] = useState<ProjectProfile[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<RunWithDetails | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(
    window.localStorage.getItem(USER_STORAGE_KEY),
  );
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    window.localStorage.getItem(PROJECT_STORAGE_KEY),
  );
  const [submitting, setSubmitting] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    if (selectedUserId) {
      window.localStorage.setItem(USER_STORAGE_KEY, selectedUserId);
    }
    void refreshProjects(selectedUserId);
    void refreshRuns(selectedUserId, selectedProjectId);
  }, [selectedUserId]);

  useEffect(() => {
    if (selectedProjectId) {
      window.localStorage.setItem(PROJECT_STORAGE_KEY, selectedProjectId);
    }
    void refreshRuns(selectedUserId, selectedProjectId);
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedRunId) {
      return;
    }
    void refreshSelectedRun(selectedRunId);
    const source = subscribeToRunEvents(selectedRunId, () => {
      void refreshSelectedRun(selectedRunId);
      void refreshRuns(selectedUserId, selectedProjectId);
    });
    return () => source.close();
  }, [selectedRunId, selectedUserId, selectedProjectId]);

  async function bootstrap() {
    const [nextUsers] = await Promise.all([fetchUsers(), refreshRuns(selectedUserId, selectedProjectId)]);
    setUsers(nextUsers);
    const chosenUser = selectedUserId ?? nextUsers[0]?.id ?? null;
    setSelectedUserId(chosenUser);
    await refreshProjects(chosenUser);
  }

  async function refreshRuns(userId?: string | null, projectId?: string | null) {
    const nextRuns = await fetchRuns({ userId, projectId });
    setRuns(nextRuns);
    if (!selectedRunId && nextRuns.length > 0) {
      setSelectedRunId(nextRuns[0].id);
    }
  }

  async function refreshSelectedRun(runId: string) {
    try {
      const detail = await fetchRun(runId);
      setSelectedRun(detail);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load run");
    }
  }

  async function refreshProjects(userId?: string | null) {
    const nextProjects = await fetchProjects(userId);
    setProjects(nextProjects);
    if (!selectedProjectId && nextProjects.length > 0) {
      setSelectedProjectId(nextProjects[0].id);
    }
  }

  async function handleSubmit(payload: CreateRunPayload) {
    setSubmitting(true);
    setError(null);
    try {
      const created = await createRun(payload);
      setSelectedRunId(created.id);
      await refreshRuns(selectedUserId, selectedProjectId);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to create run");
    } finally {
      setSubmitting(false);
    }
  }

  async function withAction(action: () => Promise<void>) {
    setWorking(true);
    setError(null);
    try {
      await action();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Action failed");
    } finally {
      setWorking(false);
      await refreshRuns(selectedUserId, selectedProjectId);
      if (selectedRunId) {
        await refreshSelectedRun(selectedRunId);
      }
    }
  }

  async function handleCreateUser() {
    const name = window.prompt("User name");
    if (!name) return;
    const user = await createUser(name);
    const nextUsers = await fetchUsers();
    setUsers(nextUsers);
    setSelectedUserId(user.id);
  }

  async function handleCreateProject() {
    const name = window.prompt("Project name");
    if (!name) return;
    const repoPath = window.prompt("Project repo path");
    if (!repoPath) return;
    const project = await createProject({
      name,
      repo_path: repoPath,
      user_id: selectedUserId,
    });
    await refreshProjects(selectedUserId);
    setSelectedProjectId(project.id);
  }

  const selectedProject = projects.find((item) => item.id === selectedProjectId) ?? null;

  return (
    <div className="app-shell">
      <div className="toolbar">
        <div className="toolbar-group">
          <label>
            <span>User</span>
            <select
              value={selectedUserId ?? ""}
              onChange={(event) => setSelectedUserId(event.target.value || null)}
            >
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="secondary-button" onClick={() => void handleCreateUser()}>
            New user
          </button>
        </div>

        <div className="toolbar-group">
          <label>
            <span>Project</span>
            <select
              value={selectedProjectId ?? ""}
              onChange={(event) => setSelectedProjectId(event.target.value || null)}
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="secondary-button" onClick={() => void handleCreateProject()}>
            New project
          </button>
        </div>
      </div>

      <div className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">Autonomous AI coding agent platform</p>
          <h1>Vibe Coder</h1>
          <p className="hero-text">
            Runs execute in isolated workspaces, stream live events, queue safely, support
            retry and cancel controls, and require diff approval before commit.
          </p>
        </div>
        <TaskForm
          onSubmit={handleSubmit}
          submitting={submitting}
          selectedUserId={selectedUserId}
          selectedProject={selectedProject}
        />
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="workspace-grid">
        <RunList runs={runs} selectedRunId={selectedRunId} onSelectRun={setSelectedRunId} />
        <RunDetail
          run={selectedRun}
          working={working}
          onCancel={(runId) => withAction(() => cancelRun(runId).then(() => undefined))}
          onRetry={(runId) => withAction(async () => setSelectedRunId((await retryRun(runId)).id))}
          onResume={(runId) => withAction(async () => setSelectedRunId((await resumeRun(runId)).id))}
          onApprove={(runId, approved) => withAction(() => approveRun(runId, approved).then(() => undefined))}
          onCommit={(runId) => withAction(() => createCommit(runId).then(() => undefined))}
        />
      </div>
    </div>
  );
}
