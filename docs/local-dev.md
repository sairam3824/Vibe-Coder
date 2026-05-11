# Local Development

## Prerequisites

- Python 3.12+
- Node 20+
- Docker
- A valid `OPENROUTER_API_KEY`

Use the same Python interpreter for installation and runtime. In this repository the safest pattern is:

```bash
python -m pip install -e .
```

## Environment

1. Copy `.env.example` to `.env`.
2. Fill in `OPENROUTER_API_KEY`.
3. Adjust optional values like `OPENROUTER_BASE_URL`, `SANDBOX_DEFAULT_IMAGE`, and `WEB_ORIGIN` as needed.

## Backend

Install and run:

```bash
python -m pip install -e .
python -m uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API creates the SQLite database automatically under `runtime/`.

If `python -m pip install -e .` succeeds but `uvicorn ...` fails with missing modules, you are likely mixing Python interpreters. Always start the server with:

```bash
python -m uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

That guarantees `uvicorn` runs under the same interpreter that installed the package.

Useful endpoints:

- `GET /health`
- `POST /api/runs`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/diff`
- `POST /api/runs/{run_id}/commit`
- `GET /api/runs/{run_id}/events`

## Frontend

Install and run:

```bash
cd apps/web
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Production build:

```bash
npm run build
```

## Tests

Run backend tests with:

```bash
pytest
```

## Docker Sandbox Notes

Validation commands run inside Docker containers with the target repo mounted at `/workspace`.

Current behavior:

- Python-heavy repos use `python:3.12-slim`
- JS/TS-heavy repos use `node:20-bookworm-slim`
- mixed repos default based on detected languages plus selected command profile

If your target repo needs additional system dependencies, set a different base image in `.env` or extend the sandbox runner.

## Example Run Request

Use the API directly:

```bash
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d @fixtures/sample_run_request.json
```
