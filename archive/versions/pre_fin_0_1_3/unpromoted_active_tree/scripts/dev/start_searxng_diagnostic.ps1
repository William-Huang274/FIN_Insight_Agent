[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$composePath = Join-Path $repoRoot "deploy/searxng-diagnostic/docker-compose.yml"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker_cli_not_available"
}

$dockerInfo = docker info --format '{{json .ServerVersion}}' 2>$null
if ($LASTEXITCODE -ne 0 -or -not $dockerInfo) {
    throw "docker_linux_daemon_not_available"
}

$secretBytes = New-Object byte[] 32
$random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $random.GetBytes($secretBytes)
} finally {
    $random.Dispose()
}
$env:SEARXNG_SECRET = [BitConverter]::ToString($secretBytes).Replace("-", "").ToLowerInvariant()

try {
    docker compose -f $composePath up -d
    if ($LASTEXITCODE -ne 0) {
        throw "searxng_diagnostic_compose_start_failed"
    }
    docker compose -f $composePath ps
} finally {
    Remove-Item Env:SEARXNG_SECRET -ErrorAction SilentlyContinue
}
