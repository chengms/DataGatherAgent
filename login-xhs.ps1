$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    python scripts\xhs_login_only.py
}
finally {
    Pop-Location
}
