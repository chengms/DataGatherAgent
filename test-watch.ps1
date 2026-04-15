$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$watch = Join-Path $root "scripts\\run_with_watch.py"

python $watch --timeout 1800 --idle-timeout 300 --heartbeat 30 --cwd $backend -- python -m unittest discover -s tests -v
