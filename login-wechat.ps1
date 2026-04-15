$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    python scripts\wechat_terminal_login.py
}
finally {
    Pop-Location
}
