param(
    [string]$Version = "",
    [string]$InstallRoot = ".tmp_node"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$InstallRootPath = Join-Path $RepoRoot $InstallRoot
$DownloadDir = Join-Path $InstallRootPath "downloads"
New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Index = Invoke-RestMethod -Uri "https://nodejs.org/dist/index.json" -TimeoutSec 30
    $Release = $Index |
        Where-Object { $_.lts -ne $false -and $_.files -contains "win-x64-zip" } |
        Select-Object -First 1
    if (-not $Release) {
        throw "No Windows x64 LTS Node release found in nodejs.org index."
    }
    $Version = $Release.version
}

$ZipName = "node-$Version-win-x64.zip"
$ZipPath = Join-Path $DownloadDir $ZipName
$ShaPath = Join-Path $DownloadDir "SHASUMS256-$Version.txt"
$ExtractDir = Join-Path $InstallRootPath "node-$Version-win-x64"

if (-not (Test-Path $ZipPath)) {
    Invoke-WebRequest -Uri "https://nodejs.org/dist/$Version/$ZipName" -OutFile $ZipPath -TimeoutSec 120
}
if (-not (Test-Path $ShaPath)) {
    Invoke-WebRequest -Uri "https://nodejs.org/dist/$Version/SHASUMS256.txt" -OutFile $ShaPath -TimeoutSec 60
}

$Expected = ((Get-Content $ShaPath | Where-Object { $_ -match [regex]::Escape($ZipName) }) -split "\s+") | Select-Object -First 1
$Actual = (Get-FileHash $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Actual -ne $Expected) {
    throw "SHA256 mismatch for $ZipName"
}

if (-not (Test-Path $ExtractDir)) {
    Expand-Archive -Path $ZipPath -DestinationPath $InstallRootPath -Force
}

$NodeExe = Join-Path $ExtractDir "node.exe"
$NpmCmd = Join-Path $ExtractDir "npm.cmd"

Write-Output "NODE_HOME=$ExtractDir"
Write-Output "NODE_EXE=$NodeExe"
Write-Output "NPM_CMD=$NpmCmd"
Write-Output "NODE_VERSION=$(& $NodeExe --version)"
Write-Output "NPM_VERSION=$(& $NpmCmd --version)"
Write-Output 'For this shell:'
Write-Output ('  $env:Path = "{0};" + $env:Path' -f $ExtractDir)
