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

- Unified bootstrap Windows PowerShell: `./bootstrap.ps1`
- Unified bootstrap Linux/macOS/WSL: `./bootstrap.sh`
- Windows PowerShell: `./start.ps1`
- Linux/macOS/WSL: `./start.sh`
- Full stack Windows PowerShell: `./up.ps1`
- Full stack Linux/macOS/WSL: `./up.sh`
- WeChat terminal login: `./login-wechat.ps1` or `./login-wechat.sh`
- Xiaohongshu terminal login: `./login-xhs.ps1` or `./login-xhs.sh`

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

To bootstrap a fresh machine end to end, use:

```bash
./bootstrap.sh
```

or on Windows:

```powershell
.\bootstrap.ps1
```

The bootstrap flow will:

- scan required commands and repositories
- install backend and external tool dependencies
- start a temporary WeChat service if a QR login is needed
- render QR codes in the terminal for WeChat and Xiaohongshu when credentials are missing
- persist the resulting login state to `services.local.json`
- launch the full stack after login is complete

If credentials are already saved and you only want to bring the stack online, use:

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
- `bootstrap.ps1` / `bootstrap.sh` is the preferred first-run entrypoint
- `up.ps1` / `up.sh` is the normal day-to-day restart entrypoint once credentials exist

## Current Scope

This MVP implements the workflow skeleton:

1. keyword input
2. article discovery
3. article fetch
4. AI relevance scoring
5. hot article ranking

The adapter layer now supports two integration modes:

- in-process adapters, such as the current mock and lightweight web adapters
- external-tool adapters, which are designed to call mature crawler repositories from a managed checkout on disk

Workflow preview requests now default to platform-driven source selection. The frontend uses this mode and only sends selected `platforms`.

Current platform strategies:

- `wechat` -> `wechat_exporter_search` + `wechat_exporter_fetch`
- `xiaohongshu` -> `xiaohongshu_external_search` + `xiaohongshu_external_fetch`
- `weibo` -> `weibo_external_search` + `weibo_external_fetch`
- `douyin` -> `douyin_external_search` + `douyin_external_fetch`
- `bilibili` -> `bilibili_external_search` + `bilibili_external_fetch`

For single-platform API calls, you can still pass explicit `discovery_source` and `fetch_source`.

`wechat_exporter_search` and `wechat_exporter_fetch` are now wired for service-mode integration against a self-hosted `wechat-article-exporter` instance.

Required environment variables:

- `WECHAT_EXPORTER_BASE_URL`
- `WECHAT_EXPORTER_API_KEY`

For one-click local startup, copy `services.local.example.json` to `services.local.json` and place the API key there if you do not want to export it in your shell.

Terminal login helpers are available for the managed external tools:

- `login-wechat.ps1` / `login-wechat.sh` requests a QR code from the local `wechat-article-exporter` service, renders it in the terminal, waits for your scan confirmation, and stores the resulting `WECHAT_EXPORTER_API_KEY` in `services.local.json`
- `login-xhs.ps1` / `login-xhs.sh` launches the managed `MediaCrawler` Xiaohongshu login flow, renders the QR code in the terminal, and stores the resulting cookie string in `services.local.json`

Typical first-run flow:

1. run `bootstrap.ps1` or `bootstrap.sh`
2. scan the WeChat QR code if prompted
3. scan the Xiaohongshu QR code if prompted
4. wait for credentials to be written to `services.local.json`
5. let the script finish bringing the full stack online

The managed launcher now checks for:

- required binaries such as `python`, `node`, and `yarn`
- required environment values such as `WECHAT_EXPORTER_API_KEY`
- occupied ports before startup
- HTTP health endpoints when configured
- clean upstream checkouts before attempting fast-forward updates

The managed stack now covers two external repositories:

- `wechat-article-exporter` as the WeChat service on port `3000`
- `MediaCrawler` as the Xiaohongshu-oriented managed crawler service on port `8080`

`xiaohongshu_external_search` and `xiaohongshu_external_fetch` execute through a local wrapper script that runs inside the managed `MediaCrawler` checkout without editing upstream files. Optional runtime variables for that path are:

- `XHS_MEDIACRAWLER_LOGIN_TYPE`
- `XHS_MEDIACRAWLER_COOKIES`
- `DATA_GATHER_BROWSER_HEADLESS` (defaults to `true`, recommended for servers)
- `MEDIACRAWLER_HEADLESS` (legacy alias for the same behavior)

`weibo_external_*`, `douyin_external_*`, and `bilibili_external_*` run through `scripts/mediacrawler_platform_runner.py` using the same managed `MediaCrawler` checkout.

`GET /api/discovery/sources` returns both discovery and fetch adapters with their `kind` and `live` flags.

Available discovery sources:

- `mock_wechat_search`
- `web_search_wechat`
- `wechat_exporter_search`
- `xiaohongshu_external_search`
- `weibo_external_search`
- `douyin_external_search`
- `bilibili_external_search`

Available fetch sources:

- `mock_wechat_fetch`
- `web_fetch_wechat`
- `wechat_exporter_fetch`
- `xiaohongshu_external_fetch`
- `weibo_external_fetch`
- `douyin_external_fetch`
- `bilibili_external_fetch`

Workflow executions are persisted to SQLite.

- Linux default: `backend/data/workflow.sqlite3`
- Current Windows development default: `%USERPROFILE%\.codex\memories\data-gather-agent.sqlite3`
- Override with `DATA_GATHER_DB_PATH`
