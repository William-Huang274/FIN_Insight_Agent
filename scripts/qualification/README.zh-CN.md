# 成熟控制面 qualification 最小复现说明

本目录只用于 2026-08-31 成熟栈资格实验，不是生产运行入口，也不是新的 FIN 控制协议。

准确边界：runner 调用的是仓库真实 `financial_facts` 代码路径，但输入是手工、确定性的 DELL-shaped PIT fixture。它包含占位 URL、digest、observation 和 accession；因此 `real_source_replay=false`、`data_correctness_qualification=false`、`source_admission=false`。本实验只验证控制面能否运行同一 FIN 语义切片、记录失败/重试和读回观测产物。

当前提交的 `requirements.lock` 是 lab-only、Python 3.13、277 个包的 hash lock，SHA-256 为 `EC3CCBD13D2A51ACC3A067B3706E6F11747C7A79CBE99702D13A137256198782`。它与实际 Z 盘实验锁（SHA-256 `5E252AEFEF18946160692F4A396AB6315F9B34942D8402BA543768CB4189DC1E`）的 277 个 package/version 条目完全一致；文件 hash 因生成命令头和输入注释不同而不同。当前 lock 已知有 3 个安全 finding，不得直接晋升为 production lock。

## 1. 建立隔离环境

以下命令从仓库根目录运行。`$qualificationRoot` 必须位于 `Z:\FIN_Insight_Agent_qualification` 下；建议每次使用新目录，避免覆盖原始证据。

```powershell
$qualificationRoot = 'Z:\FIN_Insight_Agent_qualification\replay_control_plane_slice_v1'
$repositoryRoot = 'D:\FIN_Insight_Agent'
$basePython = 'C:\Users\hht13\AppData\Local\Programs\Python\Python313\python.exe'
$qualificationPython = Join-Path $qualificationRoot 'env\Scripts\python.exe'

$env:UV_CACHE_DIR = Join-Path $qualificationRoot 'cache\uv'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONPATH = "$repositoryRoot;$repositoryRoot\src"

New-Item -ItemType Directory -Path $qualificationRoot -Force | Out-Null
uv venv (Join-Path $qualificationRoot 'env') --python $basePython
uv pip sync (Join-Path $repositoryRoot 'scripts\qualification\requirements.lock') --python $qualificationPython
```

`PYTHONPATH` 只在当前 PowerShell 进程中暴露已检出的仓库代码；不要把本地 editable distribution 塞进 277-package exact 环境。复现时必须同时记录 `git rev-parse HEAD`，否则 lock 相同也不能证明运行了同一版 FIN 代码。

## 2. 固定状态目录并启动 MLflow

```powershell
$prefectHome = Join-Path $qualificationRoot 'state\prefect'
$prefectMemoStore = Join-Path $prefectHome 'memo_store.toml'
$dagsterHome = Join-Path $qualificationRoot 'state\dagster'
New-Item -ItemType Directory -Path $prefectHome, $dagsterHome -Force | Out-Null

$env:PREFECT_HOME = $prefectHome
$env:PREFECT_SERVER_MEMO_STORE_PATH = $prefectMemoStore
$env:PREFECT_SERVER_ALLOW_EPHEMERAL_MODE = 'true'
Remove-Item Env:PREFECT_API_URL -ErrorAction SilentlyContinue
Remove-Item Env:PREFECT_SERVER_DATABASE_CONNECTION_URL -ErrorAction SilentlyContinue

$env:DAGSTER_HOME = $dagsterHome
@"
telemetry:
  enabled: false
"@ | Set-Content -LiteralPath (Join-Path $dagsterHome 'dagster.yaml') -Encoding utf8

$mlflow = & (Join-Path $repositoryRoot 'scripts\qualification\start_mlflow_for_qualification.ps1') `
    -QualificationRoot $qualificationRoot
$mlflow
```

launcher 最多等待 30 秒确认 `/health`；进程提前退出或超时会 fail closed，并指向 Z 盘日志。

两个 workflow adapter 会再次 fail closed 校验 `PREFECT_HOME`、`PREFECT_SERVER_MEMO_STORE_PATH` 和 `DAGSTER_HOME` 是否精确指向本次 qualification 根目录中的状态位置；Prefect adapter 同时拒绝外部 API/database URL override。

## 3. 运行同一 fixture、DVC 和测试

```powershell
& $qualificationPython -m scripts.qualification.run_dagster_fin_control_plane_slice `
    --qualification-root $qualificationRoot `
    --mlflow-tracking-uri $mlflow.TrackingUri

& $qualificationPython -m scripts.qualification.run_prefect_fin_control_plane_slice `
    --qualification-root $qualificationRoot `
    --mlflow-tracking-uri $mlflow.TrackingUri

& $qualificationPython -m scripts.qualification.run_dvc_fin_artifact_roundtrip `
    --qualification-root $qualificationRoot `
    --dvc-executable (Join-Path $qualificationRoot 'env\Scripts\dvc.exe')

& $qualificationPython -m pytest -q `
    'tests\qualification' `
    'tests\test_s2_company_financial_fact_mart.py::test_exact_lookup_is_point_in_time_and_preserves_vintages'
```

首次 transient failure 是 fixture runner 刻意注入的，候选必须使用自身 retry 机制恢复；它不是金融数据错误。OpenLineage 的 START/COMPLETE 只覆盖成功 attempt，workflow 自身日志负责证明前一 attempt 的 retry 状态。

## 4. 生成供应链证据

```powershell
$manifestRoot = Join-Path $qualificationRoot 'manifests'
New-Item -ItemType Directory -Path $manifestRoot -Force | Out-Null

& (Join-Path $qualificationRoot 'env\Scripts\cyclonedx-py.exe') environment `
    $qualificationPython --output-reproducible --output-format JSON `
    --output-file (Join-Path $manifestRoot 'sbom.cdx.json')

& (Join-Path $qualificationRoot 'env\Scripts\pip-licenses.exe') `
    --from=mixed --format=json --with-urls `
    --output-file (Join-Path $manifestRoot 'licenses.json')

& (Join-Path $qualificationRoot 'env\Scripts\pip-audit.exe') `
    --format=json --output (Join-Path $manifestRoot 'vulnerability-audit.json')
```

`pip-audit` 返回非零时必须保留报告并按失败处理。本轮已知 finding 为 `cryptography 49.0.0 / PYSEC-2026-3552`、`diskcache 5.6.3 / PYSEC-2026-2447`、`pytest 8.4.2 / PYSEC-2026-1845`。

完成后只停止本说明启动的 MLflow 进程：

```powershell
Stop-Process -Id $mlflow.MlflowPid
```

原始成功/失败证据仍位于 `Z:\FIN_Insight_Agent_qualification\20260831_control_plane_slice_v1`；本说明不修改、迁移或重写该目录，也不触碰 `D:\FIN_Insight_Agent\data\indexes`。
