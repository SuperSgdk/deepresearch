param([ValidateRange(1, 65535)][int]$Port = 8010)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($_.OwningProcess)"
    if ($owner.CommandLine -and $owner.CommandLine.Contains("$PSScriptRoot\app")) { Stop-Process -Id $owner.ProcessId }
}
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker -and (Test-Path 'deploy/.env')) { & $docker.Source compose --env-file deploy/.env -f deploy/compose.yaml stop }
Write-Host 'Project stopped. Database volumes are preserved.'
