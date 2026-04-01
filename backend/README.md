# Backend MVP

## Run

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

Quick launchers:

- Windows PowerShell: `./start.ps1`
- Linux/macOS/WSL: `./start.sh`

After startup, open `http://127.0.0.1:8000/` for the built-in workflow console.

## API

- `GET /health`
- `GET /api/discovery/sources`
- `POST /api/workflows/preview`
- `GET /api/workflows/jobs`
- `GET /api/workflows/jobs/{job_id}`

## Frontend

The backend now serves a lightweight frontend page at `/` that can:

- inspect available search and fetch adapters
- run workflow previews
- review recent jobs and ranked articles

No separate frontend build step is required.

## Tests

Run automated tests with:

```bash
cd backend
python -m unittest discover -s tests -v
```

## Current Scope

This MVP implements the workflow skeleton:

1. keyword input
2. article discovery
3. article fetch
4. AI relevance scoring
5. hot article ranking

Current adapters are mock implementations so the workflow can run end to end before integrating real WeChat search and article crawlers.

`GET /api/discovery/sources` returns both discovery and fetch adapters with their `kind` and `live` flags.

Available discovery sources:

- `mock_wechat_search`
- `web_search_wechat`

Available fetch sources:

- `mock_wechat_fetch`
- `web_fetch_wechat`

Workflow executions are persisted to SQLite.

- Linux default: `backend/data/workflow.sqlite3`
- Current Windows development default: `%USERPROFILE%\.codex\memories\data-gather-agent.sqlite3`
- Override with `DATA_GATHER_DB_PATH`
