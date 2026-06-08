param(
    [string]$ImageTag = "finsight-workbench:backend-local",
    [int]$Port = 8765,
    [switch]$FullImage,
    [switch]$FullRuntime,
    [switch]$UsePypiHostFallback,
    [string]$PypiHostIp = "151.101.64.223",
    [switch]$UseNpmHostFallback,
    [string]$NpmRegistryHostIp = "104.16.5.34",
    [switch]$SkipBuild,
    [switch]$SkipRun,
    [switch]$SmokeOnly
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$ConfigsData = Join-Path $RepoRoot "configs"
$DataRoot = Join-Path $RepoRoot "data"
$ReportsRoot = Join-Path $RepoRoot "reports"
$WorkbenchData = Join-Path $RepoRoot "data\workbench_private"
$ContainerName = "finsight-workbench-local"
$Target = if ($FullImage) { "workbench" } else { "workbench-backend" }
$RequirementsFile = if ($FullRuntime) { "requirements.txt" } else { "requirements-workbench.txt" }
$InstallOsPackages = if ($FullRuntime) { "1" } else { "0" }
$ImageKind = if ($FullRuntime) { "runtime" } elseif ($FullImage) { "workbench" } else { "backend" }
$RuntimeProfile = if ($FullRuntime) { "integrated" } else { "control-plane" }

Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path $WorkbenchData | Out-Null
New-Item -ItemType Directory -Force -Path $ReportsRoot | Out-Null

if (-not $SkipBuild) {
    $BuildArgs = @(
        "build",
        "--target",
        $Target,
        "--build-arg",
        "REQUIREMENTS_FILE=$RequirementsFile",
        "--build-arg",
        "INSTALL_OS_PACKAGES=$InstallOsPackages",
        "--build-arg",
        "WORKBENCH_IMAGE_KIND=$ImageKind",
        "--build-arg",
        "WORKBENCH_RUNTIME_PROFILE=$RuntimeProfile",
        "-t",
        $ImageTag
    )

    if ($UsePypiHostFallback) {
        $BuildArgs += @(
            "--add-host",
            "pypi.org:$PypiHostIp",
            "--add-host",
            "files.pythonhosted.org:$PypiHostIp"
        )
    }

    if ($UseNpmHostFallback) {
        $BuildArgs += @(
            "--add-host",
            "registry.npmjs.org:$NpmRegistryHostIp"
        )
    }

    $BuildArgs += "."

    Write-Host "构建 Workbench Docker 镜像：$ImageTag，target=$Target"
    Write-Host "依赖文件：$RequirementsFile"
    if ($UsePypiHostFallback) {
        Write-Host "已启用 PyPI host fallback：$PypiHostIp"
    }
    if ($UseNpmHostFallback) {
        Write-Host "已启用 npm registry host fallback：$NpmRegistryHostIp"
    }
    & docker @BuildArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

if ($SkipRun) {
    exit 0
}

$ExistingContainer = & docker ps -aq --filter "name=^/$ContainerName$"
if ($ExistingContainer) {
    docker rm -f $ContainerName | Out-Null
}

$ConfigsMountArg = "${ConfigsData}:/app/configs"
$DataMountArg = "${DataRoot}:/app/data"
$ReportsMountArg = "${ReportsRoot}:/app/reports"
$PortArg = "127.0.0.1:${Port}:8765"

Write-Host "启动 Workbench 容器： http://127.0.0.1:$Port/"
$RunArgs = @(
    "run",
    "--rm",
    "-d",
    "--name",
    $ContainerName,
    "-p",
    $PortArg,
    "-v",
    $ConfigsMountArg,
    "-v",
    $DataMountArg,
    "-v",
    $ReportsMountArg,
    "-e",
    "WORKBENCH_IMAGE_KIND=$ImageKind",
    "-e",
    "WORKBENCH_RUNTIME_PROFILE=$RuntimeProfile",
    "-e",
    "WORKBENCH_SCRIPT_UPDATE_MODE=image_rebuild",
    "-e",
    "WORKBENCH_DATA_UPDATE_MODE=data_build_jobs",
    $ImageTag
)
$ContainerId = & docker @RunArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "container=$ContainerId"

$HealthUrl = "http://127.0.0.1:$Port/api/health"
for ($i = 1; $i -le 30; $i++) {
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $Response = & curl.exe -fsS $HealthUrl 2>$null
    $CurlExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousErrorActionPreference
    if ($CurlExitCode -eq 0) {
        Write-Host "健康检查通过：200"
        Write-Host $Response
        if ($SmokeOnly) {
            docker stop $ContainerName | Out-Null
            Write-Host "Smoke-only 模式已停止容器。"
        }
        exit 0
    }
    Start-Sleep -Seconds 2
}

Write-Host "健康检查失败，输出容器日志："
docker logs $ContainerName
if ($SmokeOnly) {
    docker stop $ContainerName | Out-Null
}
exit 1
