param(
    [ValidateSet("Dev", "Built")]
    [string]$Mode = "Dev",
    [string]$HostName = "127.0.0.1",
    [int]$BackendPort = 8765,
    [int]$FrontendPort = 5173,
    [string]$FixtureRoot = ".codex_runtime\vt2-demo-20260718\canonical-runtime",
    [string]$Python = "python",
    [string]$Node = "",
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$FrontendRoot = Join-Path $RepoRoot "apps\workbench\frontend"
$RuntimeRoot = Join-Path $RepoRoot ".codex_runtime\internal-alpha"
$FixturePath = if ([IO.Path]::IsPathRooted($FixtureRoot)) { $FixtureRoot } else { Join-Path $RepoRoot $FixtureRoot }
$FixturePath = (Resolve-Path -LiteralPath $FixturePath).Path
$BaselineStore = Join-Path $RuntimeRoot "human-baseline.sqlite3"
$StatePath = Join-Path $RuntimeRoot "workbench-processes.json"

function Resolve-Executable {
    param([string]$Explicit, [string]$Name, [string]$Bundled)
    if ($Explicit) {
        if (Test-Path -LiteralPath $Explicit) { return (Resolve-Path -LiteralPath $Explicit).Path }
        $ExplicitCommand = Get-Command $Explicit -ErrorAction SilentlyContinue
        if ($ExplicitCommand) { return $ExplicitCommand.Source }
        throw "$Name executable not found: $Explicit"
    }
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($Command) { return $Command.Source }
    if ($Bundled -and (Test-Path -LiteralPath $Bundled)) { return $Bundled }
    throw "$Name executable was not found. Pass -$Name with an explicit path."
}

function Test-Endpoint {
    param([string]$Uri)
    try {
        $Response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 2
        return $Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500
    }
    catch { return $false }
}

function Wait-Endpoint {
    param([string]$Uri, [int]$Seconds = 30)
    for ($Index = 0; $Index -lt $Seconds * 2; $Index++) {
        if (Test-Endpoint -Uri $Uri) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out waiting for $Uri"
}

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

if (Test-Path -LiteralPath $StatePath) {
    $Existing = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    $BackendAlive = $Existing.backend_pid -and (Get-Process -Id $Existing.backend_pid -ErrorAction SilentlyContinue)
    $FrontendAlive = $Mode -eq "Built" -or ($Existing.frontend_pid -and (Get-Process -Id $Existing.frontend_pid -ErrorAction SilentlyContinue))
    if ($BackendAlive -and $FrontendAlive) {
        Write-Host "FinSight Internal Alpha is already running: $($Existing.url)"
        if ($OpenBrowser) { Start-Process $Existing.url }
        exit 0
    }
}

$PythonExe = Resolve-Executable -Explicit $Python -Name "python" -Bundled ""
$NodeFallback = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
$NodeExe = Resolve-Executable -Explicit $Node -Name "node" -Bundled $NodeFallback

if ($Mode -eq "Built") {
    Push-Location $FrontendRoot
    try {
        & $NodeExe "node_modules\typescript\bin\tsc" -p "tsconfig.json"
        if ($LASTEXITCODE -ne 0) { throw "TypeScript build failed." }
        & $NodeExe "node_modules\vite\bin\vite.js" build --config "vite.config.ts"
        if ($LASTEXITCODE -ne 0) { throw "Vite build failed." }
    }
    finally { Pop-Location }
}

$BackendOut = Join-Path $RuntimeRoot "backend.out.log"
$BackendErr = Join-Path $RuntimeRoot "backend.err.log"
$BackendArgs = @(
    (Join-Path $RepoRoot "scripts\workbench\start_workbench.py"),
    "--host", $HostName,
    "--port", [string]$BackendPort,
    "--fixture-root", $FixturePath,
    "--baseline-store", $BaselineStore
)
$Backend = Start-Process -FilePath $PythonExe -ArgumentList $BackendArgs -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $BackendOut -RedirectStandardError $BackendErr -PassThru

$Frontend = $null
if ($Mode -eq "Dev") {
    $FrontendOut = Join-Path $RuntimeRoot "frontend.out.log"
    $FrontendErr = Join-Path $RuntimeRoot "frontend.err.log"
    $FrontendArgs = @(
        (Join-Path $FrontendRoot "node_modules\vite\bin\vite.js"),
        "--config", (Join-Path $FrontendRoot "vite.config.ts"),
        "--host", $HostName,
        "--port", [string]$FrontendPort,
        "--strictPort"
    )
    $Frontend = Start-Process -FilePath $NodeExe -ArgumentList $FrontendArgs -WorkingDirectory $FrontendRoot -WindowStyle Hidden -RedirectStandardOutput $FrontendOut -RedirectStandardError $FrontendErr -PassThru
}

$Url = if ($Mode -eq "Dev") { "http://${HostName}:$FrontendPort/tasks" } else { "http://${HostName}:$BackendPort/tasks" }
$State = [ordered]@{
    schema_version = "fin_ia_internal_alpha_process_state_v1"
    mode = $Mode
    backend_pid = $Backend.Id
    frontend_pid = if ($Frontend) { $Frontend.Id } else { $null }
    backend_url = "http://${HostName}:$BackendPort"
    url = $Url
    fixture_root = $FixturePath
    baseline_store = $BaselineStore
    started_at = [DateTimeOffset]::Now.ToString("o")
}
$State | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8

try {
    Wait-Endpoint -Uri "http://${HostName}:$BackendPort/api/health"
    Wait-Endpoint -Uri $Url
}
catch {
    Write-Error "Workbench failed to start. Inspect $BackendErr and the frontend error log under $RuntimeRoot."
    throw
}

Write-Host "FinSight Internal Alpha is running."
Write-Host "  Product UI: $Url"
Write-Host "  API:        http://${HostName}:$BackendPort"
Write-Host "  Logs/state: $RuntimeRoot"
Write-Host "  Exact human baseline store: $BaselineStore"
if ($OpenBrowser) { Start-Process $Url }
