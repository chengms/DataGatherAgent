$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    python scripts\bootstrap_stack.py @args
}
finally {
    Pop-Location
}
