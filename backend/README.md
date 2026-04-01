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

## API

- `GET /health`
- `GET /api/discovery/sources`
- `POST /api/workflows/preview`
- `GET /api/workflows/jobs`
- `GET /api/workflows/jobs/{job_id}`

## Current Scope

This MVP implements the workflow skeleton:

1. keyword input
2. article discovery
3. article fetch
4. AI relevance scoring
5. hot article ranking

Current adapters are mock implementations so the workflow can run end to end before integrating real WeChat search and article crawlers.

Available discovery sources:

- `mock_wechat_search`
- `web_search_wechat`

Available fetch sources:

- `mock_wechat_fetch`
- `web_fetch_wechat`

Workflow executions are persisted to SQLite.

- Linux 默认：`backend/data/workflow.sqlite3`
- 当前 Windows 开发环境默认：`%USERPROFILE%\\.codex\\memories\\data-gather-agent.sqlite3`
- 也可以用环境变量 `DATA_GATHER_DB_PATH` 覆盖
