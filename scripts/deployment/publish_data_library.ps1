param(
    [Parameter(Mandatory=$true)][string]$SettingsDirectory,
    [Parameter(Mandatory=$true)][string]$SnapshotDirectory,
    [switch]$Plan
)
$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$settingsPath = (Resolve-Path -LiteralPath $SettingsDirectory).Path
$snapshotPath = (Resolve-Path -LiteralPath $SnapshotDirectory).Path
$nodesPath = Join-Path $snapshotPath 'retrieval_nodes.jsonl'
if (!(Test-Path -LiteralPath $nodesPath -PathType Leaf)) { throw 'Source snapshot missing' }
if (!(Test-Path -LiteralPath (Join-Path $settingsPath 'host-settings.json'))) { throw 'Workbench settings missing' }
$libraryPath = [IO.Path]::GetFullPath((Join-Path $settingsPath 'attachments/public-library'))
if (!$libraryPath.StartsWith($settingsPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Library path outside selected settings directory' }
$digest = (Get-FileHash -LiteralPath $nodesPath -Algorithm SHA256).Hash.ToLowerInvariant()
$pythonPath = Join-Path $repoPath '.venv/Scripts/python.exe'
Write-Output "Snapshot: $digest"
Write-Output "Public library destination: $libraryPath"
Write-Output 'Actions: retain snapshot; reload existing Docker Agent Server; restart only the verified 18795 workbench; check health and data APIs. No model calls.'
if ($Plan) { return }
$sessions = Invoke-RestMethod 'http://127.0.0.1:18795/api/v1/research-sessions'
if (@($sessions | Where-Object status -eq 'busy').Count -gt 0) { throw 'Research is running; wait before deployment' }
$conversations = Invoke-RestMethod 'http://127.0.0.1:18795/api/v1/conversations'
if (@($conversations | Where-Object status -eq 'busy').Count -gt 0) { throw 'Conversation is running; wait before deployment' }
$listener = Get-NetTCPConnection -LocalPort 18795 -State Listen | Select-Object -First 1
$backendProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
if (!$backendProcess -or $backendProcess.CommandLine -notmatch 'scripts.deployment.research_workbench.*serve' -or $backendProcess.CommandLine -notmatch [regex]::Escape($repoPath)) { throw '18795 is not the expected repository workbench' }
$snapshotDestination = Join-Path $libraryPath "snapshots/$digest"
New-Item -ItemType Directory -Path $snapshotDestination -Force | Out-Null
foreach ($file in Get-ChildItem -LiteralPath $snapshotPath -File) {
    if ($file.Name -match '^[a-f0-9]{64}\.html$|^(retrieval_nodes\.jsonl|documents\.json|plan\.json|receipts\.json)$') {
        Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $snapshotDestination $file.Name)
    }
}
$activeNodes = Join-Path $libraryPath 'retrieval_nodes.jsonl'
if (Test-Path -LiteralPath $activeNodes) {
    $oldDigest = (Get-FileHash -LiteralPath $activeNodes -Algorithm SHA256).Hash.ToLowerInvariant()
    Copy-Item -LiteralPath $activeNodes -Destination (Join-Path $libraryPath "previous-$oldDigest.jsonl")
}
Copy-Item -LiteralPath $nodesPath -Destination $activeNodes
Push-Location $repoPath
try {
    & $pythonPath -X utf8 -m scripts.deployment.research_workbench up --no-build --settings-directory $settingsPath --enable-research --fresh-only --semantic-memory --hermes --hybrid-rag
    if ($LASTEXITCODE -ne 0) { throw 'Agent Server deployment failed; workbench was not stopped' }
    Stop-Process -Id $backendProcess.ProcessId
    $logRoot = Join-Path $libraryPath ('deployment-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Path $logRoot | Out-Null
    $serverArgs = @('-X','utf8','-m','scripts.deployment.research_workbench','serve','--settings-directory',('"'+$settingsPath+'"'),'--enable-research','--fresh-only','--semantic-memory','--hermes','--hybrid-rag','--ui-port','18795')
    $process = Start-Process -FilePath $pythonPath -ArgumentList $serverArgs -WorkingDirectory $repoPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot 'stdout.log') -RedirectStandardError (Join-Path $logRoot 'stderr.log') -PassThru
    $healthy=$false
    for ($attempt=0; $attempt -lt 25; $attempt++) {
        Start-Sleep -Seconds 2
        try { $health=Invoke-RestMethod 'http://127.0.0.1:18795/api/health'; $healthy=$health.status -eq 'ok' } catch { $healthy=$false }
        if ($healthy) { break }
    }
    if (!$healthy) { throw "Workbench did not become healthy; logs: $logRoot" }
    $sources=Invoke-RestMethod 'http://127.0.0.1:18795/api/v1/data-library/sources?ticker=MSFT&year=2024'
    $financials=Invoke-RestMethod 'http://127.0.0.1:18795/api/v1/data-library/financials?ticker=MSFT&fiscal_year=2025'
    if ($sources.total -lt 1 -or $financials.total -lt 1) { throw 'Published coverage check failed' }
    Write-Output "Ready: MSFT FY2024 documents=$($sources.total); FY2025 financial rows=$($financials.total); workbench parent=$($process.Id)"
    Write-Output 'Open http://127.0.0.1:18795/workspace/session?view=library'
} finally { Pop-Location }
