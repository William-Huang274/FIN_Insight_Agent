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

## 5. 2026-08-31 locked control-plane profile 与真实 S2 vertical

旧 277-package lock 继续只复现早期候选比较，不再作为 production candidate。仓库根 `pyproject.toml` / `uv.lock` 现在是唯一依赖源；默认 profile不安装工作流引擎，显式 `control-plane` extra提供运行时，`qualification` extra只提供测试 runner所需的 psycopg 3。最终支持结论仍须由 fresh locked env与最终 clean commit收据签发：

```powershell
$qualificationRoot = 'Z:\FIN_Insight_Agent_qualification\replay_postgres_dagster_s2_v1'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $qualificationRoot 'env-final-qualification-py311'
$env:UV_CACHE_DIR = Join-Path $qualificationRoot 'cache\uv'
$env:UV_PYTHON_DOWNLOADS = '0'

uv sync --locked --no-dev --extra control-plane --extra qualification --no-install-project `
    --python 'Z:\FIN_Insight_Agent_qualification\20260831_production_dependency_and_vertical_v1\python\cpython-3.11.14-windows-x86_64-none\python.exe'

$env:PYTHONPATH = 'D:\FIN_Insight_Agent;D:\FIN_Insight_Agent\src'
& (Join-Path $env:UV_PROJECT_ENVIRONMENT 'Scripts\python.exe') `
    -m scripts.qualification.run_postgres_dagster_s2_fact_mart_vertical `
    --qualification-root $qualificationRoot `
    --host-port 55432
```

前置要求不只有 Docker：仓库必须 clean；解释器必须位于同一 Z 盘 qualification root；必须从根 `uv.lock` fresh sync `control-plane + qualification`；Git、policy、tracked result和 runner绑定文件必须存在；`data/raw_private` 还必须预先物化 policy列出的 DELL/MU/NVDA 12 个 capture/metadata对象并通过 digest校验。另需可用 Docker daemon、未占用 loopback port，以及已拉取并按 digest固定的 official PostgreSQL image。runner每次创建独立 container/network/data/secret，验证 native transaction、UNIQUE、advisory lock、restart、host-roundtrip custom dump/restore、Dagster PostgreSQL run/event storage和一条真实 local source-bound S2 CompanyFacts materialization。结束时只移除本 attempt拥有的 container/network与 ephemeral secret；成功、失败、数据库目录和 dump均留在 Z 盘。

这里有两种不能混写的成熟Docker拓扑：本Windows runner的client在宿主进程中，因此使用attempt专属普通bridge，并把PostgreSQL精确发布到`127.0.0.1`；Engine回读必须证明driver、`Internal=false`、loopback binding、attempt label与唯一network attachment，并在container启动后再次证明实际`NetworkSettings.Ports`只有这一条loopback映射。它限制的是数据库宿主暴露面，不是zero-egress或air-gap。CI中的client和PostgreSQL都在container内，仍使用internal network且不发布数据库host port。未来若要更强隔离，应另行资格化“runner也容器化”的成熟拓扑，不在本修正里引入自研proxy或防火墙编排。

当前 exact image：

```text
postgres@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685
```

`20260831T034026Z-a8700e1b` 与后续 `040515` 只代表当时代码的历史 bounded PASS；它们没有绑定当前 hardened adapter、runtime inventory、cleanup与 host-roundtrip restore，不能称为最终 replay。`20260831T094310Z-ac7fd1d9`又证明clean binding和cleanup，但因Windows host-runner误用internal network而在host PostgreSQL连接处失败，同样不能升级为PASS。

网络修正commit `d127e327...`上的`20260831T110518Z-a77be8f5`已证明loopback bridge、PostgreSQL事务/锁/重启、binding、secret scan与cleanup，但在执行S2 builder前发现current-bound v1.1结果的历史claimed digest不可从持久化对象重算。runner v1.2只允许canonical tracked path、exact file SHA、claimed/canonical三元组以及runtime registry R39／policy v1.14／receipt v1.15同时匹配时，将它作为shadow parity输入；receipt必须写`self_digest_valid=false`、`current_s2_authority_self_integrity_pass=false`和`current_s2_authority_migration_authorized=false`。所有fresh legacy/Dagster结果继续走正常self-digest validator，不能进入该兼容入口。

builder与Workbench默认结果已改写到`data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/v1/company_financial_fact_mart_result.json`；tracked v1.0与current-bound v1.1均禁止作为新输出目标。最终 exact attempt必须在producer/harness修正提交后，从该新clean commit和全新 locked qualification环境用新attempt ID重跑，再在本节填入。

即使最终 `status=bounded_engineering_pass`，它也只证明本地 PostgreSQL 16.15 profile与一条 Dagster outer-workflow adapter；不授权 production cutover、Evidence/S2 bridge、R14、LangGraph、report/product/release，也不把 Dagster storage当作金融事实权威。schedule/sensor user state在本纵切中不适用且未测。用于非Compose部署时，把 `configs/control_plane/dagster.postgres.yaml`复制到独立可写的`DAGSTER_HOME/dagster.yaml`，并把 PostgreSQL URL通过平台secret或只读文件交给`DAGSTER_POSTGRES_URL_FILE`；不要把明文URL或密码提交到Git。

Docker 的 opt-in Compose profile为 `control-plane`。它把 `${FINSIGHT_CONTROL_PLANE_DATA_MOUNT:-./data/raw_private}`只读挂到`/app/data/raw_private`，把输出写入独立state volume；真实job使用`configs/control_plane/s2_fact_mart_shadow.run_config.example.yaml`。Compose secret的宿主source是环境变量`DAGSTER_POSTGRES_URL`，容器只收到`/run/secrets/dagster_postgres_url`文件；launcher不会接受旧的Compose明文environment映射。最小启动形状是：

```powershell
$env:DAGSTER_POSTGRES_URL = 'postgresql://USER:PERCENT_ENCODED_PASSWORD@HOST:5432/DB'
$env:FINSIGHT_IMAGE_REVISION = (git rev-parse HEAD)
if (git status --porcelain) { throw 'Compose image build requires a clean worktree' }
docker compose --profile control-plane config --quiet
docker compose --profile control-plane up --build control-plane
```

不要执行会打印resolved model的普通`docker compose config`。默认Compose不再映射任何provider API key；曾被旧配置展开过的EIA credential必须在外部提供方轮换，仓库修复不能替代轮换。直接`docker run`时，secret file必须让容器UID 10001可读；CI/qualification必须实际证明读取成功，不能只凭Compose字段推断权限。

原始成功/失败证据仍位于 `Z:\FIN_Insight_Agent_qualification\20260831_control_plane_slice_v1`；本说明不修改、迁移或重写该目录，也不触碰 `D:\FIN_Insight_Agent\data\indexes`。
