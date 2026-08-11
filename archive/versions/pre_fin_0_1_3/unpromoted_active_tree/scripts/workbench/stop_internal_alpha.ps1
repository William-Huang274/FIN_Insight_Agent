param()

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$StatePath = Join-Path $RepoRoot ".codex_runtime\internal-alpha\workbench-processes.json"

if (-not (Test-Path -LiteralPath $StatePath)) {
    Write-Host "No FinSight Internal Alpha process state was found."
    exit 0
}

$State = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
foreach ($ProcessId in @($State.frontend_pid, $State.backend_pid)) {
    if (-not $ProcessId) { continue }
    $Process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if (-not $Process) { continue }
    $CommandLine = [string]$Process.CommandLine
    $IsWorkbench = $CommandLine.Contains($RepoRoot, [StringComparison]::OrdinalIgnoreCase) -and (
        $CommandLine.Contains("start_workbench.py", [StringComparison]::OrdinalIgnoreCase) -or
        $CommandLine.Contains("vite.config.ts", [StringComparison]::OrdinalIgnoreCase)
    )
    if (-not $IsWorkbench) {
        throw "Refusing to stop PID $ProcessId because its command line is not owned by this workspace."
    }
    Stop-Process -Id $ProcessId
    Write-Host "Stopped PID $ProcessId."
}

Remove-Item -LiteralPath $StatePath
Write-Host "FinSight Internal Alpha stopped. Human baseline records and logs were retained."
