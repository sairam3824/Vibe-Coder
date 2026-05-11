# Vibe Coder Architecture

## Overview

Vibe Coder is a local-first autonomous coding agent platform for trusted repositories. The current build is structured as a Python monorepo with a FastAPI backend, a React frontend, and modular packages for orchestration, sandboxing, git operations, repository parsing, and typed schemas.

The system flow is:

1. A local user selects or creates a project and submits a run request.
2. The API persists the run in `QUEUED` state.
3. A background worker dequeues the run, prepares an isolated workspace, and executes the LangGraph workflow.
4. The agent scans the repository, builds import/test context, generates a plan, applies targeted or full-file edits, validates them inside Docker, and iterates on failures.
5. Events, approvals, metrics, validation attempts, file changes, and final artifacts are persisted to SQLite.
6. The frontend streams live updates via SSE and exposes controls for cancel, retry, resume, approval, and commit.

## Repository Layout

```text
apps/
  api/        FastAPI application
  web/        Vite React application
packages/
  agent/      LangGraph orchestration, prompts, editing logic
  gitops/     Git utilities, commit helpers, workspace isolation
  parsers/    Language detection and Tree-sitter-backed symbol extraction
  sandbox/    Docker-based validation execution
  schemas/    Shared Pydantic models used across the backend
docs/         Architecture, prompting, local development, security notes
tests/        Unit and integration tests
```

## Backend Components

### API Layer

FastAPI exposes endpoints to:

- create/list users and projects
- create/list runs
- fetch run status/details and diffs
- cancel, retry, and resume runs
- approve or reject a diff
- trigger commit creation
- stream run events over server-sent events

The API uses SQLAlchemy with SQLite for persistence and a single-worker queue for safe serialized execution in the MVP.

### Persistence

SQLite tables capture:

- `users`
- `projects`
- `runs`
- `events`
- `plans`
- `file_changes`
- `validation_attempts`
- `commit_artifacts`
- `approvals`

Pragmatic SQLite migrations are applied at startup for the MVP.

### Orchestration And Queueing

The orchestrator:

- queues new runs
- creates isolated per-run workspaces
- supports cancel/retry/resume semantics
- blocks commit creation until approval
- updates persisted metrics and events as the run progresses

Workspace isolation uses:

- `git worktree add --detach` for git repositories
- filesystem copy fallback for non-git repositories

### Agent Workflow

The agent is a LangGraph state machine with these nodes:

- `ingest_task`
- `scan_repo`
- `select_relevant_files`
- `extract_context`
- `plan_changes`
- `apply_changes`
- `run_validation`
- `analyze_failures`
- `repair_changes`
- `finalize_run`

Loop guards:

- maximum iteration count
- duplicate failure signature detection
- no-op edit detection
- cancellation checks between major steps

### Model Provider

The provider layer wraps OpenRouter chat completions and handles:

- configurable base URL
- auth headers
- optional referer/app name headers
- retries and backoff
- timeout handling
- normalized response parsing
- token usage capture when returned

### Repo Understanding

Repository analysis combines:

- language/framework heuristics from manifests
- file map generation
- git metadata capture
- Tree-sitter symbol extraction for Python and TS/JS/TSX/JSX
- lightweight import graph extraction
- test-to-source mapping heuristics
- small relevant context chunks for prompts

### Editing

The editing engine can:

- read and write files safely under a run workspace
- create new files
- track before/after content
- compute unified diffs
- apply targeted patch operations such as snippet replacement, append/prepend, and insert-after anchors

The default edit path still supports full-file rewrites when the model response makes that safer for the current MVP.

### Validation Sandbox

All validation commands execute through Docker. The sandbox runner:

- mounts the target repo read-write
- uses a configurable base image strategy
- executes bootstrap/setup commands before validation when useful
- executes commands with timeout
- captures stdout/stderr/exit code/duration
- avoids privileged mode

The default command profiles cover common Python and Node repositories, with per-run overrides.

## Frontend

The web app provides:

- local user and project selection
- task submission form
- model, iteration, approval, and validation controls
- run list and history
- live event display via SSE
- cancel, retry, resume, approve, and commit controls
- changed file list
- validation attempt output
- metrics and final result summaries

## Trust And Safety Assumptions

This build is intended for local or self-hosted use on trusted repositories only. Docker isolation is best-effort and not a hard security boundary. Workspace isolation reduces repo-to-repo interference, but operators must still avoid exposing sensitive repositories or credentials unnecessarily.
