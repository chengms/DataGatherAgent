$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    python scripts\xhs_terminal_login.py
}
finally {
    Pop-Location
}
