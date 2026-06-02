param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8765,
    [string]$Python = "python",
    [switch]$Reload,
    [switch]$SkipFrontendBuild,
    [switch]$InstallNode,
    [string]$NodeInstallRoot = ".tmp_node"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$FrontendRoot = Join-Path $RepoRoot "apps\workbench\frontend"
$WorkbenchData = Join-Path $RepoRoot "data\workbench_private"

function Find-Npm {
    param([string]$InstallRoot)

    $LocalRoot = Join-Path $RepoRoot $InstallRoot
    if (Test-Path $LocalRoot) {
        $LocalNpm = Get-ChildItem -Path $LocalRoot -Directory -Filter "node-v*-win-x64" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            ForEach-Object { Join-Path $_.FullName "npm.cmd" } |
            Where-Object { Test-Path $_ } |
            Select-Object -First 1
        if ($LocalNpm) {
            return $LocalNpm
        }
    }

    $PathNpm = Get-Command npm -ErrorAction SilentlyContinue
    if ($PathNpm) {
        return $PathNpm.Source
    }
    return $null
}

Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path $WorkbenchData | Out-Null

if (-not $SkipFrontendBuild) {
    $Npm = Find-Npm -InstallRoot $NodeInstallRoot
    if (-not $Npm -and $InstallNode) {
        Write-Host "未找到 npm，开始安装项目内 Node..."
        & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "install_node_local.ps1") -InstallRoot $NodeInstallRoot | Write-Host
        $Npm = Find-Npm -InstallRoot $NodeInstallRoot
    }

    if ($Npm) {
        $NodeHome = Split-Path -Parent $Npm
        $env:Path = "$NodeHome;$env:Path"
        Push-Location $FrontendRoot
        try {
            if (-not (Test-Path (Join-Path $FrontendRoot "node_modules"))) {
                Write-Host "安装 Workbench 前端依赖..."
                if (Test-Path (Join-Path $FrontendRoot "package-lock.json")) {
                    & $Npm ci
                }
                else {
                    & $Npm install
                }
            }
            Write-Host "构建 Workbench 前端..."
            & $Npm run build
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Warning "未找到 npm。将跳过 React/Vite 前端构建，后端会使用内置静态页面。需要自动安装 Node 时请加 -InstallNode。"
    }
}

$StartArgs = @(
    (Join-Path $RepoRoot "scripts\workbench\start_workbench.py"),
    "--host",
    $HostName,
    "--port",
    [string]$Port
)
if ($Reload) {
    $StartArgs += "--reload"
}

Write-Host ""
Write-Host "FinSight Workbench 即将启动："
Write-Host ("  http://{0}:{1}/" -f $HostName, $Port)
Write-Host ""
& $Python @StartArgs
