# FinSight Workbench 前端与本地工作台规划

本文档定义 FinSight-Agent 下一阶段的图形化工作台路线。目标不是给现有命令行包一层一次性界面，而是把数据源配置、链路运行、证据检查、会话调试和评测入口沉淀成可长期维护的本地研究工作台。

## 定位

FinSight Workbench 是 FinSight-Agent 的本地/私有部署工作台，面向三类场景：

- 项目展示：让读者直观看到 Agent 如何从问题进入研究任务解析、证据检索、数值台账、覆盖检查、模型综合和规则校验。
- 自测迭代：让开发者不用反复手写命令行，就能切换数据 profile、模型路由、测试用例和会话。
- 自有数据接入：让克隆仓库的人能通过图形化检查知道自己还缺哪些 manifest、索引、8-K 或市场快照产物。

Workbench 不负责取代底层 Agent。模型调用、证据处理、上下文管理、评测和规则校验仍由现有 Python 模块负责；前端只是把这些能力组织成可操作、可检查、可复用的工作流。

## 当前项目基础

当前仓库已经具备可复用的后端能力：

- 单轮入口：`scripts/cloud/sec_agent_interactive.sh ask-full-source-api`
- 多轮入口：`scripts/cloud/sec_agent_interactive.sh session-full-source-api`
- profile 加载：`SEC_AGENT_PROFILE_ENV=.env`
- 模型路由：`LLM_BACKEND`、`BASE_URL`、`MODEL_NAME`、`API_KEY_ENV`
- 上下文管理：`src/sec_agent/context_manager.py`
- 工具调用与执行：`src/sec_agent/tool_controller.py`、`src/sec_agent/tool_harness.py`
- 市场快照：`src/sec_agent/market_snapshot.py`、`scripts/market/*`
- 发布/结构检查：`scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py`
- 图运行状态：`sec_agent_state.json`、阶段 artifact refs、`run_data_fingerprint.json`、`run_performance.json`

因此第一版 Workbench 应优先复用这些能力，避免新写一条和 CLI 不一致的链路。

## 设计原则

1. **模块优先，不做 shell 拼接产品。**
   后端 API 应优先调用 Python service/module；长任务可以临时 subprocess 调现有脚本，但每个 subprocess 都要有后续模块化目标。

2. **数据源是 profile，不是散落环境变量。**
   UI 操作的核心对象应是一个可验证的 workspace profile，描述 manifest、索引、source policy、market snapshot、模型路由和运行输出目录。

3. **前端不保存真实密钥。**
   UI 只保存 `API_KEY_ENV`、provider、base URL、model name；真实 key 仍由 shell、系统环境变量或用户本机 secret store 提供。

4. **证据产物不进数据库黑箱。**
   SEC 原文、私有数据、索引、市场快照和大运行产物继续保留在现有文件/目录结构中；Workbench 数据库只保存 profile、job、run index、UI 偏好和 artifact 引用。

5. **每个阶段都要能被 CLI 验证。**
   UI 的每个按钮都应对应一个可测试的后端 endpoint 和一个可复现的命令/fixture，不能只靠手工点页面验收。

6. **单用户本地优先，多用户服务后置。**
   第一阶段可以使用本地 SQLite 和 JSON session store；任何多用户并发或 SaaS 说法必须等 DB/Redis/事务锁完成后再声明。

7. **为未来信息源预留扩展点。**
   SEC 10-K/10-Q、8-K、market snapshot 只是当前 scope。后续 transcript、IR presentation、industry news、consensus、internal notes 应通过 source adapter 接入同一套证据分层和覆盖检查。

## 目标架构

```text
浏览器 UI
  -> FastAPI Workbench Backend
      -> Profile Manager
      -> Source Readiness Service
      -> Model Route Validator
      -> Agent Run Service
      -> Session Service
      -> Artifact Viewer
      -> Eval/Smoke Runner
      -> Telemetry Stream
  -> 现有 Python Agent 能力
      query_contract / tool_controller / tool_harness
      context_manager / market_snapshot / readiness eval
      scripts/cloud/sec_agent_interactive.py
```

推荐目录：

```text
apps/workbench/
  backend/
    app.py
    api/
    services/
    schemas/
  frontend/
    index.html
    static/
    package.json
    vite/
      src/

src/sec_agent/workbench/
  profiles.py
  source_readiness.py
  job_runner.py
  artifact_index.py
```

如果项目暂时不想引入 `apps/`，也可以先把后端 service 放在 `src/sec_agent/workbench/`，前端放在 `web/workbench/`。关键不是目录名，而是保持 API contract 与现有 Agent 模块解耦。

## 数据与状态存储

### Workbench 元数据

建议使用 SQLite：

```text
data/workbench_private/workbench.sqlite
```

该路径应保持 Git ignored。当前 `.gitignore` 已忽略 `*.sqlite`，后续可以补充 `/data/workbench_private/`。

SQLite 只保存：

- profile 名称、路径、source policy、artifact refs
- job 状态、开始/结束时间、退出码、stdout/stderr 摘要
- run id、session id、answer id、artifact index
- UI 展示偏好和最近使用 profile

不保存：

- API key
- SEC 原文全文
- 数据供应商原始输出
- BM25/ObjectBM25/BGE 索引内容
- 大模型完整长输出副本，除非该输出已经作为现有 artifact 落盘

### Agent 产物

第一阶段继续复用现有产物路径：

```text
eval/sec_cases/outputs/
reports/quality/
reports/model_runs/
data/processed_private/
data/indexes/
```

Workbench 通过 artifact refs 读取这些产物，避免创建第二套运行结果格式。

## Profile Contract

Workbench profile 应从当前 `.env` 风格过渡到结构化 JSON/YAML，但第一阶段仍可兼容 `.env`。

建议结构：

```json
{
  "schema_version": "finsight_workbench_profile_v1",
  "profile_id": "local_full_source_demo",
  "display_name": "Local full-source demo",
  "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
  "model_route": {
    "llm_backend": "deepseek",
    "base_url": "https://api.deepseek.com",
    "chat_completions_path": "/chat/completions",
    "model_name": "deepseek-v4-pro",
    "api_key_env": "DEEPSEEK_API_KEY",
    "query_planner": "llm"
  },
  "sources": {
    "sec_manifest_path": "data/processed_private/manifests/...",
    "bm25_index_dir": "data/indexes/bm25/...",
    "object_bm25_index_dir": "data/indexes/bm25/...",
    "source_gap_path": "data/processed_private/source_gaps/...",
    "market_evidence_path": "data/processed_private/market/evidence_packs/...",
    "market_snapshot_id": "20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1",
    "market_as_of_date": "2026-05-22"
  },
  "runtime": {
    "python": "python",
    "bge_device": "cuda",
    "graph_execution": "in_process",
    "output_root": "eval/sec_cases/outputs",
    "execution_shell": "auto",
    "wsl_distro": null,
    "wsl_repo_root": null
  }
}
```

兼容规则：

- `.env` profile 可以被导入并显示为只读 key-value profile。
- UI 保存的新 profile 默认不写真实 key。
- profile validate 不要求所有数据源都存在，但必须明确给出 missing、warn、pass。
- Windows 本地可以把 `execution_shell` 设置为 `wsl`，让 Workbench 后端通过 WSL 启动完整 Agent 链路；真实 API key 只通过 `WSLENV` 按变量名透传。

## 数据包命名与归属

当前 `.env` 同时承载运行配置和数据路径，用户只能看到一串很长的文件名，很难判断“这到底是哪批公司、哪段时间、哪些来源”。Workbench 后续应把它拆成两个对象：

- **运行配置**：模型、密钥变量名、Python/WSL、BGE、输出目录。
- **数据包**：SEC 清单、BM25、ObjectBM25、8-K 缺口、市场证据、行业数据、覆盖公司、覆盖年份和构建时间。

数据包编号建议用稳定、可读、可排序的规则：

```text
<市场>_<主题或范围>_<公司数>_<来源组合>_<截至日期>_v<版本>
```

示例：

```text
us_ai_full30_sec8k_market_20260522_v1
us_banking_core12_sec8k_market_20260522_v1
us_healthcare_core15_sec8k_market_20260522_v1
```

每个数据包至少记录：

```json
{
  "schema_version": "finsight_source_bundle_v1",
  "bundle_id": "us_ai_full30_sec8k_market_20260522_v1",
  "display_name": "美股 AI 30 家：SEC、8-K、三个月市场快照",
  "market": "US",
  "coverage_theme": "AI infrastructure",
  "ticker_count": 30,
  "tickers_sample": ["NVDA", "AMD", "MSFT", "AMZN", "GOOGL"],
  "source_families": ["SEC 10-K/10-Q", "8-K earnings release", "market snapshot"],
  "as_of_date": "2026-05-22",
  "artifacts": {
    "manifest_path": "data/processed_private/manifests/...",
    "bm25_index_dir": "data/indexes/bm25/...",
    "object_bm25_index_dir": "data/indexes/bm25/...",
    "source_gap_path": "data/processed_private/source_gaps/...",
    "market_evidence_path": "data/processed_private/market/evidence_packs/..."
  },
  "build": {
    "created_at": "2026-05-25T00:00:00+08:00",
    "scripts": ["download_sec_filings", "build_sec_manifest", "build_bm25_index"],
    "status": "ready"
  }
}
```

UI 展示优先级：

- 首页和运行页显示 `display_name`、公司数、来源组合、截至日期和状态。
- 展开后才显示原始路径。
- 从旧 `.env` 导入时，自动生成一个“旧配置数据包”，让用户马上能保存成可读名称。
- 保存后的运行配置只引用 `bundle_id`，不再要求用户记住每个文件名。

数据包应该写入本地私有目录：

```text
data/workbench_private/source_bundles/
```

公开仓库只保留示例模板和 schema，不提交真实私有数据路径。

## 后端 API 草案

第一版 API 先保持本地单用户：

```text
GET  /api/health
GET  /api/source-bundles
POST /api/source-bundles/import-profile
POST /api/source-bundles/validate
POST /api/source-bundles/build
GET  /api/profiles
POST /api/profiles/import-env
POST /api/profiles
GET  /api/profiles/{profile_id}
POST /api/profiles/{profile_id}/validate

POST /api/model-routes/validate

POST /api/runs/ask
POST /api/runs/smoke
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/events
GET  /api/runs/{run_id}/events/stream
GET  /api/runs/{run_id}/artifacts

POST /api/sessions
POST /api/sessions/{session_id}/turns
GET  /api/sessions/{session_id}/state
GET  /api/sessions/{session_id}/context
GET  /api/sessions/{session_id}/answer

GET  /api/artifacts/{artifact_id}
GET  /api/evals
POST /api/evals/{eval_id}/run
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/events
```

实时日志建议先用 Server-Sent Events；需要双向交互时再引入 WebSocket。

## 前端页面

### 1. Workspace / Profile

用途：把复杂数据源配置从命令行转成可验证表单。

组件：

- profile 列表
- `.env` 导入
- model route 编辑
- source policy 选择
- artifact path picker / manual path input
- API key env 检查状态

验收：

- 能导入 `configs/sec_agent_full_source_demo.env.example`
- 能显示每个 source path 是否存在
- 不显示真实 API key

### 2. Source Readiness

用途：回答“我的数据是否能跑这个 Agent？”

展示：

- manifest row count、ticker count、years、form counts、source tier counts
- BM25 / ObjectBM25 index 是否存在
- 8-K source gaps 数量和原因
- market snapshot id、as_of_date、field coverage
- full-source / SEC-only / SEC+8K / market-capable 模式差异

验收：

- 缺失路径显示 warn，而不是报 Python traceback
- 覆盖范围和 `scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py` 的 source inventory 逻辑一致

### 3. Chat / Session

用途：替代 CLI 手动输入。

能力：

- 单轮 ask
- 多轮 session
- `/state`、`/context`、`/answer` 图形化按钮
- 当前 profile、source policy、model route 固定显示
- 运行中日志和阶段状态

验收：

- 同一 prompt 在 UI 和 CLI 走同一后端链路
- 多轮 session 能显示 active session、active answer、artifact refs
- follow-up 不无故重跑完整 DAG

### 4. Run Detail

用途：让用户看到“为什么这个回答可信或不可信”。

展示：

- Query Contract
- retrieved context summary
- exact-value ledger rows
- Evidence Coverage Matrix
- Judgment Plan
- synthesis output
- deterministic gates
- rendered answer
- run performance / data fingerprint

验收：

- artifact 缺失时显示缺失项和恢复建议
- 可以从 answer citation 跳到 evidence/ledger/market row

### 5. Eval / Smoke

用途：把现有回归测试变成开发者工作台。

入口：

- local structural readiness
- context state replay
- context API smoke
- context-managed dispatch replay
- tool harness fixtures
- market main-chain smoke
- saved full-source run inspection

验收：

- 每个 eval 都有命令、状态、报告路径、stdout/stderr 摘要
- skipped/warn/pass/fail 和 CLI 报告一致
- 不能把 skipped/warn 展示成 pass

## 分阶段执行计划

### Phase 0：架构与合同冻结

目标：先确定 Workbench 的边界，不写业务 UI。

步骤：

1. 定义 `WorkbenchProfile`、`SourceReadinessReport`、`RunJob`、`ArtifactSummary` 的 Pydantic schema。
2. 梳理现有 CLI 与 Python module 的可复用点，标出必须先模块化的 subprocess。
3. 确定 `apps/workbench/` 或等价目录结构。
4. 补充 `.gitignore`：`/data/workbench_private/`、前端 build 输出、node_modules。
5. 写后端 API contract 测试夹具。

验收：

- 不启动前端也能用 Python 单测验证 schema。
- profile 能从 `.env` 样例解析成结构化对象。
- 不涉及真实 API key。

### Phase 1：后端最小可用服务

目标：先做可被 UI 调用的本地 API。

步骤：

1. 引入 FastAPI / uvicorn 依赖。
2. 实现 `/api/health`。
3. 实现 profile import/list/get/validate。
4. 实现 source readiness summary，复用 readiness/source inventory 逻辑。
5. 实现 model route validate，只检查配置和 env var 是否存在，不调用大模型。

验收：

- `pytest` 覆盖 profile parse 和 source validate。
- 使用 `configs/sec_agent_full_source_demo.env.example` 能得到可读 readiness report。
- 本地缺少私有 full-source artifact 时返回 warn，不返回 500。

### Phase 2：前端壳与 Profile/Readiness 页面

目标：先解决“别人克隆后不知道怎么配置”的问题。

步骤：

1. 增加本地 Node/npm 安装脚本，避免依赖用户系统 PATH。
2. 先保留一个由 FastAPI 同源服务的无构建前端壳，降低本地启动门槛。
3. 建 React + Vite + TypeScript 前端作为主开发入口，构建后由同一个 FastAPI 后端优先服务 `frontend/dist`。
4. 做左侧导航：Profile、Source Readiness、Chat、Run Detail、Eval。
5. 做 Profile 页面。
6. 做 Source Readiness 页面。
7. 增加空状态和缺失数据引导。

验收：

- 无数据环境下也能打开页面并显示缺失项。
- 有 `.env` profile 时能显示 source coverage。
- 前端不要求真实 API key。

### Phase 3：单轮与多轮 Agent 运行

目标：让 UI 真正能替代 CLI 做交互。

步骤：

1. 实现 job runner：后台执行受控命令，先用本地 smoke 验证 job 生命周期。
2. 实现 job event store、轮询读取接口和 SSE 运行日志流。
3. 接入单轮 ask，让 UI 复用同一个 profile contract 调现有 Agent 入口。
4. 实现 session 创建和 turn API。
5. 接入 `ContextManager`，显示 active session / answer。
6. 将 `run_root`、`state_path`、`answer_path` 写入 job index。

验收：

- 本地 smoke 不依赖私有数据或 API key，能在 UI 中看到 queued/running/completed 和 stdout 日志。
- UI 单轮 ask 与 CLI `ask-full-source-api` 使用同一 profile contract。
- UI 多轮 session 与 CLI `session-full-source-api` 的 ContextManager 行为一致。
- 中断或失败时能看到阶段、stderr tail 和可恢复路径。

### Phase 4：Artifact Viewer 与证据跳转

目标：让 Workbench 体现 Agent 的证据约束价值。

步骤：

1. 读取 saved run artifact index。
2. 展示 Query Contract、Coverage Matrix、Judgment Plan、Gate report。
3. 展示 ledger table 和 market snapshot rows。
4. 在 rendered answer 中支持 citation 跳转。
5. 支持下载或复制当前 run summary。

验收：

- answer 中至少能跳转到 evidence id、ledger row 或 market field ref。
- 缺失 artifact 显示为可诊断缺口。
- 不把私有全文一次性灌进前端大对象。

### Phase 5：Eval / Smoke 控制台

目标：把开发测试流程工作台化。

步骤：

1. 建 eval registry：每个 eval 记录名称、命令、输入、输出报告、是否需要私有数据/API。
2. 接入 local structural readiness。
3. 接入 context state replay、context API smoke、tool harness fixture。
4. 接入 saved full-source run inspection。
5. 显示 pass/warn/skipped/fail 及报告链接。

验收：

- UI 跑出的报告和 CLI 路径一致。
- skipped/warn 原因可见。
- 失败报告保留 stdout/stderr 摘要。

### Phase 6：数据源接入向导

目标：降低自有数据接入门槛，把“已有数据检查”和“新数据构建”分开，不再让用户直接面对一堆文件名。

步骤：

1. 新增数据包列表和数据包详情页，显示名称、公司数、来源组合、截至日期、构建状态和校验结果。
2. 从现有 `.env` 一键导入数据包，自动填充可读名称和路径摘要。
3. 将“准备同类数据产物”做成向导：SEC-only、SEC+8K、SEC+8K+market、行业来源。
4. 提供每一步所需输入和对应 CLI 命令，先支持复制命令，再逐步支持后台执行。
5. 把 SEC 下载、SEC 清单构建、chunk、BM25、ObjectBM25、8-K 合并、市场快照、市场证据包、行业来源下载接成受控 job。
6. 每个 job 写入事件日志、产物路径、文件计数、失败原因和下一步建议。
7. job 完成后自动生成或更新数据包，并允许绑定到运行配置。

验收：

- 用户能知道下一步缺什么，而不是只看到运行失败。
- 每个向导步骤都能复制等价 CLI 命令。
- UI 明确区分“检查已有产物”和“生成新产物”。
- 成功构建后能得到一个可读的数据包名称，不需要手工记住 manifest、索引和市场证据文件名。

当前第一批已接入网页端的受控步骤：

- SEC 下载：`scripts/data_sec/download_sec_filings.py`
- SEC manifest：`scripts/data_sec/build_sec_manifest.py`
- SEC chunks：`scripts/data_sec/build_sec_chunks.py`
- EvidenceObject：`scripts/data_retrieval/build_evidence_store.py`
- BM25：`scripts/data_retrieval/build_bm25_index.py`
- ObjectBM25：`scripts/data_retrieval/build_object_bm25_index.py`
- 8-K 下载：`scripts/data_sec/download_sec_8k_earnings.py`
- 8-K manifest：`scripts/data_sec/build_sec_8k_earnings_manifest.py`
- source gap 合并：`scripts/data_sec/merge_sec_source_gaps.py`
- Yahoo 行情快照：`scripts/market/06_download_yahoo_chart_snapshot.py`
- FMP 历史行情：`scripts/market/09_download_fmp_historical_snapshot.py`
- 市场事件窗口：`scripts/market/08_build_market_events_from_sec_manifest.py`
- FMP 估值增强：`scripts/market/07_enrich_market_snapshot_valuation_fmp.py`
- 市场快照规范化：`scripts/market/10_normalize_market_snapshot_fixture.py`
- 市场快照 catalog：`scripts/market/20_build_market_snapshot_catalog.py`
- 市场 analytics：`scripts/market/30_compute_market_analytics.py`
- market evidence pack：`scripts/market/40_build_market_evidence_pack.py`
- 市场快照校验：`scripts/market/50_validate_market_snapshot.py`
- 行业来源快照：`scripts/industry/10_download_industry_source_snapshot.py`

待接入第二批：

- 多步骤 pipeline 模板，例如“SEC+8-K+market 一键顺序执行”。
- 行业数据包校验和与 relationship graph 的绑定检查。

已完成的回填规则：

- `sec_build_manifest` -> `manifest_path`
- `sec_build_bm25_index` -> `bm25_index_dir`
- `sec_build_object_bm25_index` -> `object_bm25_index_dir`
- `sec_merge_source_gaps` -> `source_gap_path`
- `market_build_evidence_pack` -> `market_evidence_path`
- `market_normalize_snapshot` / `industry_download_source_snapshot` -> `as_of_date`

回填只在用户显式绑定数据包、任务不是 dry-run、且子进程成功退出后执行。

### Phase 7：打包与演示

目标：让它适合项目展示和个人日常测试。

步骤：

1. 增加 `scripts/workbench/start_workbench.py`。
2. 一条命令启动后端和同源前端。
3. 写 `docs/workbench/workbench_quickstart.zh-CN.md`。
4. 录制 demo 流程：导入 profile -> source readiness -> 单轮 ask -> follow-up -> artifact viewer -> eval。
5. 如果需要桌面版，再评估 Tauri/Electron 包装本地 Web app。

验收：

- 新用户可以按 quickstart 在无私有数据环境打开 UI。
- 有自有数据时可以完成一次 source validate。
- 有 API key 和 full-source artifact 时可以跑完整 chat。

### Phase 8：生产化预留

这不是第一版目标，但现在要预留接口：

- SQLite store adapter 可替换为 Postgres。
- JSON ContextManager store 可替换为 DB/Redis/file-lock store。
- job runner 可替换为 Celery/RQ/Arq。
- source adapter 可扩展到 transcript、news、consensus、IR deck。
- model provider registry 可扩展到 OpenAI、Anthropic、DeepSeek、本地 vLLM。
- frontend auth 可后置加入，不影响本地单用户模式。

## Source Adapter 设计

每个信息源都应实现统一抽象：

```text
SourceAdapter
  id
  display_name
  source_tier
  supported_claims
  required_artifacts
  validate(profile) -> SourceReadinessReport
  summarize(profile) -> SourceCoverageSummary
  artifact_refs(profile) -> list[ArtifactRef]
```

当前 adapters：

- `sec_primary_filing_adapter`
- `sec_8k_earnings_adapter`
- `market_snapshot_adapter`

未来 adapters：

- `earnings_call_transcript_adapter`
- `investor_presentation_adapter`
- `industry_news_adapter`
- `consensus_snapshot_adapter`

这样后续新增信息源时只扩展 adapter，不需要重写 UI 主流程。

## 风险与约束

- **前端提前做太复杂。** 第一版必须以 profile/readiness/chat/run-detail/eval 为主，不做泛化金融仪表盘。
- **后端只包 shell。** 允许临时 subprocess，但每个入口要记录迁移到 Python service 的计划。
- **密钥误存。** UI 只能保存 env var 名称，不能保存真实 key。
- **私有数据外泄。** artifact viewer 默认摘要化，全文按需读取，且不进入公开仓库。
- **多用户能力夸大。** JSON/SQLite 阶段只能声明本地单用户或单进程工作台。
- **和 CLI 分叉。** 所有 UI 操作必须复用同一 profile contract 和现有 harness/context/eval 逻辑。

## 第一阶段推荐任务清单

1. 新增 `src/sec_agent/workbench/profiles.py`，实现 `.env` profile parser 和 Pydantic schema。
2. 新增 `src/sec_agent/workbench/source_readiness.py`，抽出 source inventory/readiness summary。
3. 新增 `apps/workbench/backend/app.py`，提供 `/api/health`、`/api/profiles/import-env`、`/api/profiles/validate`。
4. 添加后端单测，不依赖私有 full-source 数据。
5. 新增 `scripts/workbench/install_node_local.ps1`，给 Windows 本地开发提供项目内 Node/npm。
6. 新增 `apps/workbench/frontend/`，先实现 profile/readiness 两页。
7. 补充 `docs/workbench/workbench_quickstart.zh-CN.md`。

第一阶段不做真实 Agent run UI，先把数据源接入和 readiness 这两个最大摩擦点做稳定。
