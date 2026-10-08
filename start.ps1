param(
    [switch]$WebOnly,
    [switch]$NoBrowser,
    [ValidateRange(1, 65535)][int]$Port = 8010
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Create .venv and install requirements.txt first. See README.md.' }
if (-not (Test-Path 'front/agent_front/dist/index.html')) { throw 'Build the frontend with npm ci and npm run build first. See README.md.' }
if (-not $WebOnly) {
    if (-not (Test-Path '.env') -or -not (Test-Path 'deploy/.env')) { throw 'Copy both .env.example files and configure them first. See README.md.' }
    if (Select-String -Path '.env','deploy/.env' -Pattern 'CHANGE_ME' -Quiet) { throw 'Replace CHANGE_ME in both configuration files before starting databases.' }
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        $dockerPath = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
        if (-not (Test-Path $dockerPath)) { throw 'Docker Desktop is not installed yet. See README.md.' }
    } else { $dockerPath = $docker.Source }
    function Test-DockerReady {
        $probe = New-Object System.Diagnostics.Process
        $probe.StartInfo.FileName = $dockerPath
        $probe.StartInfo.Arguments = 'info --format "{{.ServerVersion}}"'
        $probe.StartInfo.UseShellExecute = $false
        $probe.StartInfo.CreateNoWindow = $true
        $probe.StartInfo.RedirectStandardOutput = $true
        $probe.StartInfo.RedirectStandardError = $true
        try {
            $null = $probe.Start()
            if (-not $probe.WaitForExit(5000)) {
                $probe.Kill()
                $probe.WaitForExit()
                return $false
            }
            return ($probe.ExitCode -eq 0)
        } finally { $probe.Dispose() }
    }
    if (-not (Test-DockerReady)) {
        if (-not (Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue)) {
            $desktopPath = Join-Path (Split-Path (Split-Path (Split-Path $dockerPath))) 'Docker Desktop.exe'
            if (-not (Test-Path -LiteralPath $desktopPath)) {
                throw 'Docker Desktop.exe was not found. Open Docker Desktop manually and retry.'
            }
            Write-Host 'Starting Docker Desktop...'
            Start-Process -FilePath $desktopPath -WindowStyle Hidden | Out-Null
        }
        Write-Host 'Waiting for Docker engine (up to 3 minutes)...'
        $deadline = [DateTime]::UtcNow.AddMinutes(3)
        while (-not (Test-DockerReady)) {
            if ([DateTime]::UtcNow -ge $deadline) {
                throw 'Docker engine did not become ready within 3 minutes. Check Docker Desktop for errors, then retry.'
            }
            Start-Sleep -Seconds 2
        }
    }
    & $dockerPath compose --env-file deploy/.env -f deploy/compose.yaml up -d --wait
    if ($LASTEXITCODE -ne 0) { throw 'Database startup failed. Check Docker Desktop.' }
}
$baseUrl = "http://127.0.0.1:$Port"
$running = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($running) {
    foreach ($listener in $running) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        if (-not $owner.CommandLine -or -not $owner.CommandLine.Contains("$PSScriptRoot\app")) {
            throw "Port $Port belongs to another application (PID $($listener.OwningProcess)). Retry start.ps1 -Port <free port>."
        }
    }
} else {
    New-Item -ItemType Directory -Force logs | Out-Null
    $arguments = "-m uvicorn app_main:app --app-dir `"$PSScriptRoot\app`" --host 127.0.0.1 --port $Port"
    Start-Process -FilePath "$PSScriptRoot\.venv\Scripts\python.exe" -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$PSScriptRoot\logs\backend.out.log" -RedirectStandardError "$PSScriptRoot\logs\backend.err.log" | Out-Null
}
for ($i=0; $i -lt 60; $i++) {
    try {
        $health = Invoke-RestMethod "$baseUrl/health" -TimeoutSec 2
        if ($health.status -eq 'ok' -and $health.service -eq 'deepresearch-backend') { break }
        throw 'Unexpected health response.'
    } catch { Start-Sleep -Seconds 1 }
}
if ($i -eq 60) { throw 'Backend did not become healthy. Check logs.' }
Write-Host "Open $baseUrl"
Invoke-RestMethod "$baseUrl/api/local-status" | Format-List
if (-not $NoBrowser) { Start-Process $baseUrl }
