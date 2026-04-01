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
- Full stack Windows PowerShell: `./up.ps1`
- Full stack Linux/macOS/WSL: `./up.sh`

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

Monitored test launchers from the repository root:

- Windows PowerShell: `./test-watch.ps1`
- Linux/macOS/WSL: `./test-watch.sh`

The startup scripts already run with heartbeat logging and idle timeout checks via `scripts/run_with_watch.py`.

## Full Stack Startup

To start the backend together with managed external services, use:

```bash
./up.sh
```

or on Windows:

```powershell
.\up.ps1
```

Service orchestration is driven by `services.manifest.json`.

- Managed third-party repositories are cloned under `external_tools/`
- Existing managed repositories must stay clean; the launcher will only update them with fast-forward pulls
- Local overrides such as API keys belong in `services.local.json` (copy from `services.local.example.json`)

## Current Scope

This MVP implements the workflow skeleton:

1. keyword input
2. article discovery
3. article fetch
4. AI relevance scoring
5. hot article ranking

Current adapters are mock implementations so the workflow can run end to end before integrating real WeChat search and article crawlers.

The adapter layer now supports two integration modes:

- in-process adapters, such as the current mock and lightweight web adapters
- external-tool adapters, which are designed to call mature crawler repositories from a managed checkout on disk

Scaffolded external discovery adapters are already registered for:

- `wechat_exporter_search`
- `wechat_exporter_fetch`
- `xiaohongshu_external_search`

`wechat_exporter_search` and `wechat_exporter_fetch` are now wired for service-mode integration against a self-hosted `wechat-article-exporter` instance.

Required environment variables:

- `WECHAT_EXPORTER_BASE_URL`
- `WECHAT_EXPORTER_API_KEY`

For one-click local startup, copy `services.local.example.json` to `services.local.json` and place the API key there if you do not want to export it in your shell.

The managed launcher now checks for:

- required binaries such as `python`, `node`, and `yarn`
- required environment values such as `WECHAT_EXPORTER_API_KEY`
- occupied ports before startup
- HTTP health endpoints when configured
- clean upstream checkouts before attempting fast-forward updates

The managed stack now covers two external repositories:

- `wechat-article-exporter` as the WeChat service on port `3000`
- `MediaCrawler` as the Xiaohongshu-oriented managed crawler service on port `8080`

`xiaohongshu_external_search` now points at the managed `MediaCrawler` checkout. The repository lifecycle is wired, but the backend-side search command mapping is still intentionally isolated behind that adapter instead of patching upstream files.

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
