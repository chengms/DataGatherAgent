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

1. keep the external crawler in its own managed checkout under `backend/external_tools/` or point to it with an environment variable
2. implement an `ExternalDiscoveryAdapter` or `ExternalFetchAdapter`
3. convert command output into `DiscoveryCandidate` and `FetchedArticle`
4. keep repository update flow separate from the main app code so upstream updates remain manageable

Current scaffolded repository env vars:

- `DATA_GATHER_WECHAT_EXPORTER_DIR`
- `DATA_GATHER_XHS_CRAWLER_DIR`

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

1. Copy `services.local.example.json` to `services.local.json`
2. Fill in `WECHAT_EXPORTER_API_KEY`
3. Run `./up.sh` or `.\up.ps1`

The launcher fails early if:

- required binaries are missing
- required environment values are unset
- a configured port is already occupied
- a configured health endpoint never becomes healthy

## Validation Checklist

1. Run monitored tests with `test-watch.ps1` or `test-watch.sh`
2. Check `git status --short`
3. Confirm any new docs are UTF-8 and readable
4. Avoid reverting unrelated work in a dirty tree
