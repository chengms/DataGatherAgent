$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$watch = Join-Path $root "scripts\\run_with_watch.py"

Push-Location $backend
try {
    python $watch --timeout 1800 --idle-timeout 300 --heartbeat 30 --cwd $backend -- python -m pip install -e .
    python $watch --heartbeat 30 --cwd $backend -- python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
}
finally {
    Pop-Location
}
