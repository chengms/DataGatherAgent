$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    python scripts\manage_services.py stop
}
finally {
    Pop-Location
}
