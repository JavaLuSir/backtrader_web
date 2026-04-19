param(
    [string]$PythonExe = "D:\envtrader\python.exe",
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8080,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $repoRoot

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python not found: $PythonExe"
}

$reloadArg = if ($NoReload) { @() } else { @("--reload") }

Write-Host "Starting Backtrader Web..." -ForegroundColor Cyan
Write-Host "Python: $PythonExe"
Write-Host "Workdir: $repoRoot"
Write-Host "URL: http://$BindHost`:$Port"

& $PythonExe -m uvicorn btweb.main:app --host $BindHost --port $Port @reloadArg
