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

## Validation Checklist

1. Run monitored tests with `test-watch.ps1` or `test-watch.sh`
2. Check `git status --short`
3. Confirm any new docs are UTF-8 and readable
4. Avoid reverting unrelated work in a dirty tree
