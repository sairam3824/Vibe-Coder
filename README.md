# Vibe Coder

Vibe Coder is a local-first autonomous AI coding agent platform. It accepts a natural-language coding task, inspects a target repository, plans changes, edits files, validates them inside Docker, retries on failures, and surfaces a run timeline with approvals, metrics, diffs, and commit artifacts.

## Architecture

```
                         +------------------+
                         |   React + Vite   |
                         |   (apps/web)     |
                         +--------+---------+
                                  |  SSE / REST
                         +--------v---------+
                         |     FastAPI       |
                         |   (apps/api)     |
                         +--------+---------+
                                  |
              +-------------------+-------------------+
              |                   |                   |
     +--------v------+  +--------v------+  +---------v------+
     | LangGraph     |  | Git Ops       |  | Docker Sandbox |
     | Agent Engine  |  | (worktrees,   |  | (validation,   |
     | (packages/    |  |  commits)     |  |  bootstrap)    |
     |  agent)       |  +---------------+  +----------------+
     +-------+-------+
             |
     +-------v---------+
     | OpenRouter API  |
     | (model calls)   |
     +-----------------+
```

## Stack

| Layer     | Technology                                     |
| --------- | ---------------------------------------------- |
| Frontend  | React 18, Vite 5, TypeScript                   |
| Backend   | FastAPI, Uvicorn, SQLAlchemy 2, SQLite          |
| Agent     | LangGraph, OpenRouter (any model), Tree-sitter |
| Sandbox   | Docker (disposable containers)                  |
| Git       | Native git CLI via subprocess                   |

## Repository Layout

```
apps/
  api/              FastAPI backend (routes, services, models, DB)
  web/              Vite + React frontend (components, API client, styles)
packages/
  agent/            LangGraph workflow, prompt templates, editing loop
  gitops/           Git helpers, worktree isolation, commit management
  parsers/          Tree-sitter symbol extraction, language detection
  sandbox/          Docker validation runner, command profiles
  schemas/          Shared Pydantic models (runs, events, tasks, common)
configs/            Validation command profiles (JSON)
docs/               Architecture, local dev, prompting, and security notes
tests/
  unit/             Unit tests (scanner, sandbox, graph, profiles, client)
  integration/      API integration tests
runtime/            SQLite database and per-run workspaces (gitignored)
```

## What It Does

1. **Queue** -- Creates queued runs from a repo path and natural-language task.
2. **Isolate** -- Creates an isolated per-run workspace using git worktrees (or filesystem copies for non-git repos).
3. **Scan** -- Inspects the repo for manifests, languages, package managers, symbols, import graphs, test mappings, and git state.
4. **Select** -- Picks relevant files using heuristic scoring plus optional model-assisted selection.
5. **Plan** -- Generates a structured implementation plan (goal, assumptions, files, validation strategy, rollback risks).
6. **Edit** -- Applies multi-file edits via full-file rewrites or targeted patch operations (replace, append, prepend, insert_after).
7. **Validate** -- Runs bootstrap and validation commands inside disposable Docker containers.
8. **Repair** -- Detects failures, diagnoses root causes, and retries with repair prompts until success, cancellation, repeated failure, or max iterations.
9. **Approve** -- Requires diff approval before commit.
10. **Commit** -- Creates a git commit on a named branch in the workspace.
11. **Stream** -- Streams live run events to the UI via SSE and persists all artifacts to SQLite.

## Workflow (LangGraph)

```
ingest_task -> scan_repo -> select_relevant_files -> extract_context -> plan_changes -> apply_changes
                                                                                          |
                                                          +-------------------------------+
                                                          |                               |
                                                    (edits applied)                 (no-op edits)
                                                          |                               |
                                                   run_validation                   finalize_run
                                                          |
                                                   analyze_failures
                                                          |
                                                  +-------+--------+
                                                  |                |
                                           (should retry)    (give up)
                                                  |                |
                                           repair_changes    finalize_run
                                                  |
                                           run_validation -> ... (loop)
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker (for sandbox validation)
- An [OpenRouter](https://openrouter.ai/) API key

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY=your_key_here
```

### 2. Install dependencies

```bash
# Backend
python -m pip install -e .

# Frontend
cd apps/web && npm install && cd ../..
```

### 3. Start the backend

```bash
python -m uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Start the frontend (separate terminal)

```bash
cd apps/web
npm run dev -- --host 0.0.0.0 --port 5173
```

### 5. Open the app

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Health check: http://localhost:8000/health

### Alternative: Make targets

```bash
make install    # Install Python deps
make api        # Start backend
make web        # Install + start frontend
make test       # Run pytest
make lint       # Run ruff
make format     # Auto-format with ruff
make build-web  # Production frontend build
```

### Alternative: Docker Compose

```bash
docker compose up --build
```

## API Reference

| Method | Endpoint                    | Description                          |
| ------ | --------------------------- | ------------------------------------ |
| GET    | `/health`                   | Health check                         |
| GET    | `/api/runs`                 | List runs (filterable by user/project) |
| POST   | `/api/runs`                 | Create a new run                     |
| GET    | `/api/runs/{id}`            | Get run detail with all artifacts    |
| GET    | `/api/runs/{id}/diff`       | Get file diffs for a run             |
| GET    | `/api/runs/{id}/events`     | SSE stream of run events             |
| POST   | `/api/runs/{id}/cancel`     | Request run cancellation             |
| POST   | `/api/runs/{id}/retry`      | Retry a failed run                   |
| POST   | `/api/runs/{id}/resume`     | Resume a run                         |
| POST   | `/api/runs/{id}/approve`    | Approve or reject diffs              |
| POST   | `/api/runs/{id}/commit`     | Trigger commit (requires approval)   |
| GET    | `/api/meta/users`           | List local users                     |
| POST   | `/api/meta/users`           | Create a local user                  |
| GET    | `/api/meta/projects`        | List projects                        |
| POST   | `/api/meta/projects`        | Create a project                     |

### Create run payload

```json
{
  "repo_path": "/path/to/your/repo",
  "task": "Add input validation to the signup form",
  "branch_name": "codex/vibe-coder-run",
  "model": "anthropic/claude-3.7-sonnet",
  "max_iterations": 3,
  "dry_run": true,
  "require_approval": true,
  "command_profile": {
    "name": "custom",
    "commands": ["pytest", "ruff check ."]
  }
}
```

## Configuration

All settings are driven by environment variables (loaded from `.env`):

| Variable                  | Default                           | Description                         |
| ------------------------- | --------------------------------- | ----------------------------------- |
| `OPENROUTER_API_KEY`      | (required)                        | OpenRouter API key                  |
| `OPENROUTER_BASE_URL`     | `https://openrouter.ai/api/v1`   | OpenRouter endpoint                 |
| `DEFAULT_MODEL`           | `anthropic/claude-3.7-sonnet`    | Default model for agent calls       |
| `DEFAULT_MAX_ITERATIONS`  | `3`                               | Default retry limit                 |
| `DATABASE_URL`            | `sqlite:///./runtime/vibecoder.db`| SQLAlchemy database URL             |
| `APP_URL`                 | `http://localhost:8000`           | Backend URL (used in API headers)   |
| `WEB_ORIGIN`              | `http://localhost:5173`           | CORS allowed origin                 |
| `SANDBOX_DEFAULT_IMAGE`   | `python:3.12-slim`               | Docker image for Python repos       |
| `SANDBOX_NODE_IMAGE`      | `node:20-bookworm-slim`          | Docker image for Node repos         |
| `SANDBOX_TIMEOUT_SECONDS` | `900`                             | Per-command Docker timeout           |
| `LOG_LEVEL`               | `INFO`                            | Python logging level                |

## Validation Profiles

Built-in profiles in `configs/command_profiles.json`:

- **python**: `pytest`, `ruff check .`, `python -m compileall .`
- **node**: `npm test -- --runInBand`, `npm run lint`, `npm run build`
- **hybrid**: `pytest`, `npm run build`

The resolver auto-selects based on detected languages. Custom profiles can be passed per-run via the API.

## Testing

```bash
# All tests
pytest

# With coverage
pytest --cov=apps --cov=packages

# Frontend type-check + build
cd apps/web && npm run build
```

## Project Status

Vibe Coder is a fully functional local-first MVP. The end-to-end flow works: task submission, repo scanning, planning, multi-file editing, Docker-based validation, self-healing retry loops, diff approval, and commit generation.

### What works now

- End-to-end autonomous coding workflow with self-healing retry loops
- Isolated per-run workspaces via git worktrees or filesystem copies
- Docker-based validation with auto-detected command profiles and bootstrap
- Full persistence: runs, events, plans, file changes, validation attempts, metrics, approvals, commits
- Live SSE event streaming to the React UI
- Operator controls: cancel, retry, resume, approve/reject, commit
- Local users and projects for run organization
- Tree-sitter symbol extraction with regex fallback
- Import graph and test-target mapping for context selection
- Targeted patch operations (replace, append, prepend, insert_after) alongside full-file rewrites
- Token usage and step-duration metrics tracking

### Production hardening roadmap

1. Replace SQLite with PostgreSQL for concurrency and operational safety
2. Replace in-process queue with a durable job system (e.g. Celery, Temporal)
3. Add authentication, authorization, RBAC, and audit logging
4. Harden Docker sandbox: resource limits, network policy, image allowlists
5. Add repo-level locking for concurrent runs on shared infrastructure
6. Expand test coverage: cancellation timing, frontend flows, failure edge cases
7. Add observability: structured tracing, dashboards, alerts, error budgets
8. Deployment docs: Postgres migrations, reverse proxy, secret management, backup policies

## Limitations

- Sandbox requires Docker to be available locally
- Editing is prompt-driven, not fully AST-native
- Tree-sitter support targets Python and TS/JS families; other languages fall back to regex
- Queue is intentionally single-worker for safety and simplicity
- Users/projects are local organizational primitives, not a full auth system
- Cancellation is cooperative and may not interrupt an in-flight Docker command immediately
- Validation depends on the selected Docker base image; complex builds may need custom images

## License

See [LICENSE](./LICENSE).
