"""Exercise the operator script's preflight without publishing or restarting anything."""
from pathlib import Path
import shutil
import subprocess

import pytest


POWERSHELL = shutil.which('powershell') or shutil.which('pwsh')
SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/deployment/publish_data_library.ps1'


@pytest.mark.skipif(not POWERSHELL, reason='PowerShell is required for the Windows operator entry')
@pytest.mark.parametrize('scenario,expected', [
    ('cold', 'COLD'), ('online', 'RELOAD'), ('research_busy', 'Research is running'),
    ('conversation_busy', 'Conversation is running'), ('foreign', 'not the expected'),
    ('native_busy', 'Native research is running'), ('native_idle', 'COLD'),
    ('docker_down', 'Docker engine is unavailable'), ('api_unreachable', 'unreachable'),
])
def test_preflight_selects_safe_restart_path(scenario, expected):
    command = r'''
$ErrorActionPreference='Stop'
$script:scenario='SCENARIO'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile('SCRIPT_PATH',[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'Script syntax error' }
$function=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Get-WorkbenchReloadTarget'},$true)
Invoke-Expression $function.Extent.Text
function Get-NetTCPConnection {
    param($LocalPort,$State,$ErrorAction)
    if ($LocalPort -eq 18795 -and $script:scenario -in @('online','research_busy','conversation_busy','foreign')) {
        [pscustomobject]@{OwningProcess=1234}
    }
}
function Get-CimInstance {
    param($ClassName,$Filter)
    $cmd='D:\FIN_Insight_Agent\.venv\python.exe -m scripts.deployment.research_workbench serve'
    if ($script:scenario -eq 'foreign') {$cmd='other application'}
    [pscustomobject]@{ProcessId=1234;CommandLine=$cmd}
}
function docker {
    $global:LASTEXITCODE=0
    if ($script:scenario -eq 'docker_down') {$global:LASTEXITCODE=1}
    if ($script:scenario -in @('native_busy','native_idle','api_unreachable')) {'finsight-dell-report-workbench-langgraph-api-1'}
}
function Invoke-RestMethod {
    param($Uri,$Method,$ContentType,$Body,$TimeoutSec)
    if ($script:scenario -eq 'api_unreachable') {throw 'unreachable'}
    if (($script:scenario -eq 'research_busy' -and $Uri -match 'research-sessions') -or
        ($script:scenario -eq 'conversation_busy' -and $Uri -match 'conversations') -or
        ($script:scenario -eq 'native_busy' -and $Uri -match 'threads/search')) {
        [pscustomobject]@{status='busy'}
    }
}
try {
    $result=Get-WorkbenchReloadTarget 'D:\FIN_Insight_Agent'
    if ($result) {'RELOAD'} else {'COLD'}
} catch { $_.Exception.Message }
'''.replace('SCENARIO', scenario).replace('SCRIPT_PATH', str(SCRIPT).replace("'", "''"))
    result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', command],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout, result.stdout
