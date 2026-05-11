export type CommandProfile = {
  name: string;
  commands: string[];
  description?: string | null;
};

export type RunMetrics = {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  model_calls: number;
  step_durations: Record<string, number>;
  validation_seconds: number;
};

export type Run = {
  id: string;
  repo_path: string;
  source_repo_path: string;
  workspace_path?: string | null;
  task: string;
  status: string;
  approval_status: string;
  branch_name?: string | null;
  model?: string | null;
  max_iterations: number;
  dry_run: boolean;
  command_profile?: CommandProfile | null;
  user_id?: string | null;
  project_id?: string | null;
  base_run_id?: string | null;
  queue_position?: number | null;
  metrics: RunMetrics;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
};

export type RunEvent = {
  id?: number | null;
  run_id: string;
  event_type: string;
  message: string;
  payload: Record<string, unknown>;
  step?: string | null;
  iteration: number;
  created_at: string;
};

export type FileChange = {
  path: string;
  change_type: string;
  summary: string;
  diff_text: string;
  iteration: number;
  approved?: boolean | null;
};

export type ValidationCommandResult = {
  command: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  duration_seconds: number;
  timed_out: boolean;
};

export type ValidationAttempt = {
  iteration: number;
  profile_name: string;
  commands: string[];
  bootstrap_commands: string[];
  success: boolean;
  results: ValidationCommandResult[];
  failure_signature?: string | null;
};

export type PlanArtifact = {
  goal_summary: string;
  assumptions: string[];
  files_likely_to_change: string[];
  validation_strategy: string[];
  rollback_risks: string[];
};

export type RepoSnapshot = {
  repo_path: string;
  is_git_repo: boolean;
  git_branch?: string | null;
  git_status: string[];
  manifests: Record<string, string>;
  languages: string[];
  frameworks: string[];
  package_managers: string[];
  files: string[];
  symbols: Record<string, Array<Record<string, string | number>>>;
  import_graph: Record<string, string[]>;
  test_targets: Record<string, string[]>;
};

export type RunWithDetails = Run & {
  repo_snapshot?: RepoSnapshot | null;
  plan?: PlanArtifact | null;
  changed_files: FileChange[];
  validation_attempts: ValidationAttempt[];
  events: RunEvent[];
  final_summary: Record<string, unknown>;
};

export type UserProfile = {
  id: string;
  name: string;
  created_at: string;
};

export type ProjectProfile = {
  id: string;
  name: string;
  repo_path: string;
  user_id: string;
  created_at: string;
};

export type CreateRunPayload = {
  repo_path: string;
  task: string;
  branch_name?: string;
  model?: string;
  max_iterations: number;
  dry_run: boolean;
  user_id?: string;
  project_id?: string;
  require_approval: boolean;
  command_profile?: CommandProfile | null;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });

  if (!response.ok) {
    const maybeJson = await response.text();
    throw new Error(maybeJson || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchRuns(filters?: { userId?: string | null; projectId?: string | null }) {
  const params = new URLSearchParams();
  if (filters?.userId) params.set("user_id", filters.userId);
  if (filters?.projectId) params.set("project_id", filters.projectId);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<Run[]>(`/runs${suffix}`);
}

export function fetchRun(runId: string) {
  return request<RunWithDetails>(`/runs/${runId}`);
}

export function createRun(payload: CreateRunPayload) {
  return request<Run>("/runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function cancelRun(runId: string) {
  return request<{ ok: boolean }>(`/runs/${runId}/cancel`, {
    method: "POST",
  });
}

export function retryRun(runId: string) {
  return request<Run>(`/runs/${runId}/retry`, {
    method: "POST",
  });
}

export function resumeRun(runId: string) {
  return request<Run>(`/runs/${runId}/resume`, {
    method: "POST",
  });
}

export function approveRun(runId: string, approved: boolean, note?: string) {
  return request<{ run_id: string; approval_status: string }>(`/runs/${runId}/approve`, {
    method: "POST",
    body: JSON.stringify({ approved, note }),
  });
}

export function createCommit(runId: string, message?: string) {
  return request<Record<string, unknown>>(`/runs/${runId}/commit`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function fetchUsers() {
  return request<UserProfile[]>("/meta/users");
}

export function createUser(name: string) {
  return request<UserProfile>("/meta/users", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function fetchProjects(userId?: string | null) {
  const suffix = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<ProjectProfile[]>(`/meta/projects${suffix}`);
}

export function createProject(payload: { name: string; repo_path: string; user_id?: string | null }) {
  return request<ProjectProfile>("/meta/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function subscribeToRunEvents(runId: string, onEvent: (event: RunEvent) => void) {
  const source = new EventSource(`${API_BASE}/runs/${runId}/events`);
  source.onmessage = (message) => {
    onEvent(JSON.parse(message.data) as RunEvent);
  };
  return source;
}
