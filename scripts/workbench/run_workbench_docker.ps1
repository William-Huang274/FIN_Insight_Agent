param(
    [string]$ImageTag = "finsight-workbench:backend-local",
    [int]$Port = 8765,
    [switch]$FullImage,
    [switch]$UsePypiHostFallback,
    [string]$PypiHostIp = "151.101.64.223",
    [switch]$SkipBuild,
    [switch]$SkipRun,
    [switch]$SmokeOnly
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$WorkbenchData = Join-Path $RepoRoot "data\workbench_private"
$ContainerName = "finsight-workbench-local"
$Target = if ($FullImage) { "workbench" } else { "workbench-backend" }

Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path $WorkbenchData | Out-Null

if (-not $SkipBuild) {
    $BuildArgs = @(
        "build",
        "--target",
        $Target,
        "--build-arg",
        "REQUIREMENTS_FILE=requirements-workbench.txt",
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

    $BuildArgs += "."

    Write-Host "构建 Workbench Docker 镜像：$ImageTag，target=$Target"
    if ($UsePypiHostFallback) {
        Write-Host "已启用 PyPI host fallback：$PypiHostIp"
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

$MountArg = "${WorkbenchData}:/app/data/workbench_private"
$PortArg = "${Port}:8765"

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
    $MountArg,
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
