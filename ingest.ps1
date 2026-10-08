param([string]$InputDirectory = "$PSScriptRoot\knowledge")
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& .\.venv\Scripts\python.exe app/mult_agents/rag/ingest.py $InputDirectory
if ($LASTEXITCODE -ne 0) { throw 'Knowledge ingestion failed.' }
