param(
    [Parameter(Mandatory = $true)]
    [string]$QualificationRoot
)

$resolvedRoot = [System.IO.Path]::GetFullPath($QualificationRoot)
$allowedRoot = [System.IO.Path]::GetFullPath('Z:\FIN_Insight_Agent_qualification')
$allowedPrefix = $allowedRoot.TrimEnd('\') + '\'
if (-not $resolvedRoot.StartsWith($allowedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "QualificationRoot must be below $allowedRoot"
}

$mlflowExecutable = Join-Path $resolvedRoot 'env\Scripts\mlflow.exe'
if (-not (Test-Path -LiteralPath $mlflowExecutable -PathType Leaf)) {
    throw "MLflow executable not found: $mlflowExecutable"
}

$stateDirectory = Join-Path $resolvedRoot 'state\mlflow'
$databasePath = (Join-Path $stateDirectory 'mlflow.db').Replace('\', '/')
$artifactDirectory = Join-Path $resolvedRoot 'artifacts\mlflow'
$artifactUri = 'file:///' + $artifactDirectory.Replace('\', '/')
$logDirectory = Join-Path $resolvedRoot 'logs'
New-Item -ItemType Directory -Path $stateDirectory, $artifactDirectory, $logDirectory -Force | Out-Null

$arguments = @(
    'server',
    '--backend-store-uri', "sqlite:///$databasePath",
    '--artifacts-destination', $artifactUri,
    '--host', '127.0.0.1',
    '--port', '55050',
    '--workers', '1'
)

$process = Start-Process `
    -FilePath $mlflowExecutable `
    -ArgumentList $arguments `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDirectory 'mlflow-server.stdout.log') `
    -RedirectStandardError (Join-Path $logDirectory 'mlflow-server.stderr.log') `
    -PassThru

$trackingUri = 'http://127.0.0.1:55050'
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ($process.HasExited) {
        throw "MLflow exited before becoming ready; inspect $logDirectory"
    }
    try {
        Invoke-RestMethod -Uri ($trackingUri + '/health') -TimeoutSec 2 | Out-Null
        $ready = $true
        break
    }
    catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    Stop-Process -Id $process.Id
    throw "MLflow did not become healthy within 30 seconds; inspect $logDirectory"
}

[pscustomobject]@{
    MlflowPid = $process.Id
    TrackingUri = $trackingUri
    QualificationRoot = $resolvedRoot
}
