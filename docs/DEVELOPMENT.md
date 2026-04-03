# Development

## Project Layout

```text
backend/
  app/
    adapters/
    api/routes/
    core/
    db/
    middleware/
    repositories/
    schemas/
    services/
    web/
    main.py
  tests/
  pyproject.toml
scripts/
docs/
start.ps1
start.sh
test-watch.ps1
test-watch.sh
up.ps1
up.sh
```

## Local Run

```bash
cd backend
python -m pip install -e .
python -m uvicorn app.main:app --reload
```

Repository root convenience scripts:

- `./bootstrap.ps1`
- `./bootstrap.sh`
- `./start.ps1`
- `./start.sh`
- `./up.ps1`
- `./up.sh`

## Tests

Standard test run:

```bash
cd backend
python -m unittest discover -s tests -v
```

Monitored test run from repository root:

```bash
./test-watch.ps1
```

or:

```bash
./test-watch.sh
```

## Command Monitoring

`start.ps1` and `start.sh` already use `scripts/run_with_watch.py`.

Use the wrapper directly for any other long-running commands:

```bash
python scripts/run_with_watch.py --timeout 1800 --idle-timeout 300 --heartbeat 30 --cwd backend -- python -m unittest discover -s tests -v
```

Recommended defaults:

- installs and tests: `--timeout 1800 --idle-timeout 300 --heartbeat 30`
- dev servers: `--heartbeat 30`

## Current Conventions

- Prefer `unittest` for repository tests
- Keep adapters registered through `app/services/registry.py`
- Keep workflow request and response shapes aligned with `app/schemas/workflow.py`
- Use app-level exceptions from `app/core/exceptions.py` when domain errors need explicit API responses

## External Crawler Integration

Use `app/adapters/external_tool.py` for mature third-party crawler repositories.

The intended pattern is:

1. keep the external crawler in its own managed checkout under `external_tools/` or point to it with an environment variable
2. implement an `ExternalDiscoveryAdapter` or `ExternalFetchAdapter`
3. convert command output into `DiscoveryCandidate` and `FetchedArticle`
4. keep repository update flow separate from the main app code so upstream updates remain manageable

Current scaffolded repository env vars:

- `DATA_GATHER_WECHAT_EXPORTER_DIR`
- `DATA_GATHER_XHS_CRAWLER_DIR`

Current platform strategy mapping in `WorkflowService.PLATFORM_STRATEGIES`:

- `wechat` -> `wechat_exporter_search` + `wechat_exporter_fetch`
- `xiaohongshu` -> `xiaohongshu_external_search` + `xiaohongshu_external_fetch`
- `weibo` -> `weibo_external_search` + `weibo_external_fetch`
- `douyin` -> `douyin_external_search` + `douyin_external_fetch`
- `bilibili` -> `bilibili_external_search` + `bilibili_external_fetch`

For the service-mode WeChat exporter integration, set:

- `WECHAT_EXPORTER_BASE_URL`
- `WECHAT_EXPORTER_API_KEY`

## Managed Repositories

One-click startup is managed by `scripts/manage_services.py` and `services.manifest.json`.

Rules:

1. External repositories live under `external_tools/`
2. They are not committed into this repository
3. The launcher clones them when missing
4. If a managed repository already exists, the launcher only updates it when `git status --porcelain` is clean
5. Updates use `git pull --ff-only` so upstream merges remain straightforward

Local per-machine overrides belong in `services.local.json`.

Recommended setup:

1. Run `./bootstrap.sh` or `.\bootstrap.ps1`
2. Scan the terminal QR codes when prompted
3. Let the bootstrap flow persist credentials into `services.local.json`
4. Reuse `./up.sh` or `.\up.ps1` later for normal startup when those credentials already exist

The launcher fails early if:

- required binaries are missing
- required environment values are unset
- a configured port is already occupied
- a configured health endpoint never becomes healthy

Managed external repositories currently covered by `up.sh` / `up.ps1`:

- `wechat-article-exporter` on port `3000`
- `MediaCrawler` on port `8080`

The `MediaCrawler` integration is kept as a clean managed checkout with no local source edits so upstream pulls remain fast-forward friendly. Xiaohongshu discovery is executed through `scripts/mediacrawler_xhs_runner.py`, which overlays temporary runtime config and leaves the upstream repository clean.

Additional MediaCrawler-backed platforms (Weibo, Douyin, Bilibili) are executed through `scripts/mediacrawler_platform_runner.py` with the same "temporary overlay config + clean checkout" pattern.

Optional Xiaohongshu runtime variables:

- `XHS_MEDIACRAWLER_LOGIN_TYPE`
- `XHS_MEDIACRAWLER_COOKIES`

The terminal login scripts are implemented in this repository, not by patching the upstream checkouts:

- [xhs_terminal_login.py](/D:/MyFile/Coder/DataGatherAgent/scripts/xhs_terminal_login.py)
- [wechat_terminal_login.py](/D:/MyFile/Coder/DataGatherAgent/scripts/wechat_terminal_login.py)
- [service_env_store.py](/D:/MyFile/Coder/DataGatherAgent/scripts/service_env_store.py)
- [bootstrap_stack.py](/D:/MyFile/Coder/DataGatherAgent/scripts/bootstrap_stack.py)

Bootstrap behavior:

1. prepare repositories and install dependencies
2. if `WECHAT_EXPORTER_API_KEY` is missing, start a temporary local `wechat-article-exporter` instance and run terminal QR login
3. if `XHS_MEDIACRAWLER_COOKIES` is missing, run terminal QR login against the managed `MediaCrawler` checkout
4. persist login results to `services.local.json`
5. stop temporary bootstrap-only processes
6. launch the full stack through the normal managed service flow

Operational notes:

- `bootstrap.ps1` / `bootstrap.sh` is the preferred first-run entrypoint
- `up.ps1` / `up.sh` assumes credentials already exist
- `services.local.json` is machine-local and intentionally ignored by git

## Validation Checklist

1. Run monitored tests with `test-watch.ps1` or `test-watch.sh`
2. Check `git status --short`
3. Confirm any new docs are UTF-8 and readable
4. Avoid reverting unrelated work in a dirty tree
