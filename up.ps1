$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    python scripts\manage_services.py up
}
finally {
    Pop-Location
}
