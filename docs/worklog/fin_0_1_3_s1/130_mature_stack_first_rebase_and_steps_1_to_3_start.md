# S1 工作记录 130：成熟栈优先纠偏、旧自研协议收口与 Steps 1–3 启动

日期：2026-08-30
状态：STEPS 1–3 MATERIALIZED / QUALIFICATION EVIDENCE COMPLETE / PRODUCTION AND PRODUCT PASS FALSE

## 1. Owner 纠正

Owner 指出：产品全面迁移的第二层工程治理和第三层运行时本来应大量借鉴或直接采用成熟技术栈，但工作却再次被扩写成一套自研计划执行协议；连续一天主要在制定 Phase 0–7 文档，成熟组件测试和真实产品工作尚未开始。

Owner 随后授权：先把成熟栈优先、反无限自研和进度止损融合成 Codex 的长期 guideline，再立即开始此前说明的第一至第三步：

1. 终止并收口旧自研协议方向；
2. 用真实 FIN 代码路径上的确定性 fixture 资格验证成熟项目运行底座；
3. 完成/复核 S1–S5 全产品能力和迁移审计。

## 2. 出发点反思

旧方向的原始动机是保护 R14 的真实高风险边界：失败不可隐藏、阶段责任不后传、删除要可恢复、不可逆动作要有证据。这些原则本身仍正确。

错误发生在实现层：把针对删除和高风险运行的强控制推广到读取、计划、review、Git 和隔离实验；又把“计划可审计”误解为“必须先自研一套能授权计划本身的 runtime”。每次 review finding 继续增加状态、ticket、CAS、receipt 和 successor，最终控制面成为主要交付，产品工作被推迟。

纠正不是降低准确性，而是把通用准确性、恢复和并发交给成熟工程系统，把 FIN 的严格性集中到金融事实、Evidence、PIT、citation、人审和 release。

## 3. Step 1 已落盘的结果

- 根 `AGENTS.md` 新增成熟栈优先、三层分责、复杂度预算、docs-only 止损、按风险分级和进度分类规则；
- 新增 `docs/project_os/mature_stack_first_and_complexity_budget_policy.zh-CN.md`，作为跨任务长期记忆；
- 原 `FIN_0_1_3_PRODUCT_WIDE_ARCHITECTURE_REBASE_AND_MATURE_STACK_MIGRATION_EXECUTION_PROGRAM_20260830.zh-CN.md` 顶部标记 `SUPERSEDED / AUDIT-ONLY / NO EXECUTION AUTHORITY`，完整保留历史，不再修订其自研状态机；
- 新增一份合并的架构决定与 bounded execution baseline，记录停止原因、仍有效的不变量、重新提出有限自研的证明条件和真实 Steps 1–3；不复制运行时状态机。独立只读复核曾提醒不要让纠偏本身增加过多文档，因此没有保留分开的 ADR 与 baseline。

这部分属于治理/文档增量，不冒充成熟组件已经安装、代码已经迁移或产品能力已经增加。

## 4. Git 与不可变事实

开始时：

- canonical checkout=`D:\FIN_Insight_Agent`；
- branch=`codex/fin013-dell-s1-s2-product-bridge`；
- HEAD/upstream=`1472ecef4f02adfb51f5fcd1474dc844554ab5dd`；
- 既有未提交变更只有旧超大执行程序草案，本轮保留并原位 supersede，没有 reset 或丢弃。

R14 继续保持：

- implementation freeze=`7e25cad95ee84b39fb2a51063100405bc27da6e5`；
- preview=`27,026 total / 26,787 pass / 239 fail`；
- event/assertion=`228/11`；event mismatch=`277`；
- RC-S1-109/110 open；
- R15/R16=false，formal=false，Evidence/S2/report/release=false。

`D:\FIN_Insight_Agent\data\indexes` 未删除、未修改。只有后续实测证明 D 盘空间是 qualification blocker 时，才可按 Owner 已给出的严格有限范围另行执行。

## 5. Step 2：Z 盘真实运行、确定性 fixture qualification

隔离根：`Z:\FIN_Insight_Agent_qualification\20260831_control_plane_slice_v1`。使用 Python `3.13.7`、uv `0.10.7`，统一解析并安装 277 个 hash-locked packages；没有安装进全局 Python，没有写大型环境到 D 盘。

输入复用现有 Company Financial Fact Mart 的 DELL revenue PIT 测试语义，但它是手工、确定性的 DELL-shaped fixture，不是现场 SEC 来源回放：

- research-as-of `2026-06-01` → `40,000,000,000`；
- research-as-of `2026-08-06` → `43,842,000,000`；
- 保留 fixture 中不同 accepted-at/accession 和两个占位 source digests；
- input SHA-256=`29772d164a8258847da08efe4f589c7527308e81e4785de3f4b852b7b3f0b8d5`。

因此本节证明的是成熟控制面真实运行了 FIN fact-mart 代码路径；`real source replay=false`、`data correctness qualification=false`、`source admission=false`，不得写成 S2 或金融真值资格 PASS。

### 5.1 Workflow 对照

- Dagster `1.13.20`：第一次执行注入 `QUALIFICATION_TRANSIENT_FAILURE_INJECTED`，官方 RetryPolicy 产生 `STEP_UP_FOR_RETRY`／`STEP_RESTARTED`，最终 `RUN_SUCCESS`。Z 盘 persistent instance run=`7b4015c2-c170-4bdb-aea8-c6acb9aed5b0`，新进程 readback=`SUCCESS`，telemetry=false；当前 engine adapter 83 行，新增行只做 `DAGSTER_HOME` exact fail-closed 校验。
- Prefect `3.8.4`：第一次 task 失败后官方 `Retry 1/1`，最终 Completed。早期默认配置向 `C:\Users\hht13\.prefect` 写 memo/result；该目录全部为本轮新文件，已完整移到 Z 盘 `artifacts\prefect-unexpected-home-write` 保存证据。随后 flow/task 设置 `persist_result=False` 并显式指定 `PREFECT_HOME` 与 `memo_store.toml`，最终 run=`34c26437-b02c-4f5b-abf1-bae8d75ad3b8`，C 盘目录不存在，Z 盘状态重读 `COMPLETED`；当前 engine adapter 77 行，新增行只做 Prefect 状态路径及外部 API/database override 的 fail-closed 校验。
- 共享 qualification helper 为 401 行，高于前检提出的“约 250 行”期望值；其中包含完整 DELL-shaped typed fixture、MLflow/OTel/OpenLineage 验证、结果序列化和两个短小的环境边界 helper，未实现 scheduler、lock、retry 或状态机。它只作为测试工具提交，不得直接晋升成生产 runtime；真正 integration 仍须把观测逻辑下沉到薄 adapter/标准 instrumentation。
- 决策：Dagster 是外层数据/研究 workflow primary candidate，Prefect 是 challenger。两者都没有获得 production adoption；LangGraph 仍只针对内层 Agent graph，尚未测试。

### 5.2 共同底座与失败

- MLflow `3.15.2`：tracking server、params/metrics、artifact upload 和官方 client readback通过；最终 Prefect/Dagster run 分别为 `51bfea36a4624143830dc23e4ea0e850`／`3555f695f68a479e9aeffe9f24853135`。初始 artifact URI 缺 `file:///` 导致 HTTP 500，失败 run 保留；Windows console GBK 又暴露 emoji `UnicodeEncodeError`，设置 UTF-8 后通过。Windows job execution backend 仍提示不支持。
- OpenTelemetry `1.44.0`：每个 run 产生 `fin.control-plane-slice`、write、lookup-before、lookup-after 四个 spans，未记录正文/secret。
- OpenLineage `1.52.0`：FileTransport 产生 START/COMPLETE 两个事件且 run ID 一致；没有为“栈完整”部署第二 backend。
- DVC `3.67.1`：第一次用 `file://` 配置 Windows local remote 因路径语义失败，失败目录保留；改为受支持的绝对路径后 push 1 file，移走 workspace 文件和 `.dvc/cache`，再从 remote pull，SHA-256=`5332a6660d7e68701d47b5996e5d616a62347fb4454efa1e5d4c123ed86972e1` exact。
- PostgreSQL `18.6` target：Docker Desktop 启动因 `dockerInference` listener 路径错误失败。本轮停止重试，未 reset Docker、未拉不明镜像、未用 SQLite 冒充 transaction/lock/restart/backup proof。

### 5.3 依赖与安全证据

- `requirements.in` SHA-256=`5e35ca47ee11ea1adef95cf81858f36068b729d88f03de7b4d508cea67572f73`；lock SHA-256=`5e252aefef18946160692f4a396ab6315f9b34942d8402ba543768cb4189dc1e`；
- 仓库已加入同 277 package/version 集的 lab-only hash lock（SHA-256=`ec3ccbd13d2a51acc3a067b3706e6f11747c7a79cbe99702d13a137256198782`）、MLflow launcher 和 `scripts/qualification/README.zh-CN.md`；Prefect/Dagster adapter 对状态目录做 exact fail-closed 校验；
- CycloneDX：277 components；pip-licenses：272 packages；
- pip-audit：3 个漏洞：cryptography 49.0.0（fix 50.0.0，但 MLflow 3.15.2 要求 `<50`）、diskcache 5.6.3（无 fix）、pytest 8.4.2（fix 9.0.3）；当前 lock 不得晋升生产；
- 仅安装 `requirements.txt` 的 clean venv 共 28 packages；导入 Workbench 在 `ingestion/official_pdf.py` 因 `ModuleNotFoundError: pypdf` 失败；`playwright` 同样缺失，Pydantic 约束也从 `pyproject.toml` 的 `>=2.13,<3` 漂移为 `requirements.txt` 的 `>=2.7.0`。Docker/requirements 依赖源漂移不是推测。

qualification summary SHA-256=`c6750a23b729b80b769cb6c850a7320cded818ca9d50443f680d5c6afbea8150`。

### 5.4 磁盘和停止条件

实验目录逻辑大小约 1.94 GiB；结束时 D/Z 可用约 4.643/16.142 GiB，分别高于 4/12 GiB 停止线，lab 低于 5 GiB 预算。`D:\FIN_Insight_Agent\data\indexes` 未修改，没有空间理由触发条件式删除。

## 6. Step 3：S1–S5 迁移 reconciliation

原 Build / Adopt / Hold / Retire 能力边界继续有效，但具体控制面映射已纠正：

- 外层数据/研究/评测 pipeline：Dagster primary candidate，Prefect challenger；
- 内层 LLM Agent graph：LangGraph 后续单 vertical candidate；
- canonical transaction/lock：PostgreSQL，当前环境 blocked；
- experiment/telemetry/lineage：MLflow candidate + OTel + OpenLineage；
- durable long jobs：Temporal 继续 HOLD；
- large artifacts：DVC conditional adopt；
- FIN 继续拥有 source/as-of、Candidate/Evidence/NumericFact、PIT、admission、Gap、financial bridge、citation、人审和 release。

产品审计第 12 节已补全 S1–S5 模块级 `retain/wrap/replace/regression/retire`：R3–R14 固化为 regression；S1 通用 parser/search/index、S3 attempt runtime/provider transport、S4 generic ops、S5 dependency/IAM/observability 进入成熟 owner 迁移；S2 NumericFact/PIT/bridge 和 S3 materiality/claim/WWC 等 FIN domain kernel 保留。

## 7. 当前真实进度与下一边界

- 产品增量：0；
- 工程/资格增量：真实候选安装、两个 workflow retry/result、experiment/telemetry/lineage/DVC round-trip、依赖失败和安全审计已物化；
- 文档增量：旧协议收口、实测 delta、模块迁移基线；
- production integration：0；legacy deletion：0；R14 change：0；
- R14=`7e25cad9...`、239/277、RC-S1-109/110、R15/R16/formal/Evidence/S2/report/release 状态全部不变。

下一阶段不应继续补计划。技术上最小前置是统一 dependency source/lock、修复 PostgreSQL 资格画像，然后只接一条 Dagster vertical；是否授权这一步由 Owner 看完结果后决定。任何候选失败优先换配置/候选或保留 blocker，不自动新建 FIN 通用平台。

## 8. 作者分离 closeout 与复现修正

独立只读 reviewer 首轮判定 `FAIL_BOUNDED`，没有 P0，但指出三类真实问题：把手工 fixture 写成“真实 DELL/真实输入”、hash lock/launcher/runbook 只在 Z 盘、framework 状态路径未 fail closed。修正过程中又用 fresh README replay smoke 发现 Prefect memo store 必须是 `memo_store.toml` 文件、runner 必须以 `python -m` 启动，并且不能依赖未记录的 editable install。上述问题均在同一 qualification 工作包内修复，没有新建 runtime 或弱化验收。

最终独立 verdict=`BOUNDED PASS`，`P0/P1/P2/P3=0/0/0/1`；唯一 P3 是 `external_pattern_registry.jsonl` 的工作区 CRLF→LF 提示，Git diff 仍只有一条新增 JSONL record，内容解析有效。最终验证：

- qualification code/hash lock/replay entry commit=`b6597ba25ce705735c2310915a5e1f157b50b4a4`；
- 默认仓库环境 helper tests=`4 passed`；Z qualification 环境 helper + FIN PIT baseline=`5 passed`；
- Dagster/Prefect/DVC 三个 `python -m ... --help` fresh import smoke 全部 exit 0；
- 仓库 lab-only lock=277 package/version，SHA-256=`ec3ccbd13d2a51acc3a067b3706e6f11747c7a79cbe99702d13a137256198782`；对实际 Z env 执行 `uv pip sync --dry-run` 为 `Would make no changes`；
- PowerShell launcher AST、Python compileall、213-Python active baseline、3 份 Project OS JSONL、8,316-file secret scan 和 `git diff --check` 均 PASS；
- 全仓 pytest=`2,598 passed / 3 skipped / 0 failed`，耗时 `1,085.04s`；只有 2 条既有 SWIG type deprecation warning；
- reviewer 确认 R14、PostgreSQL blocker、3 个漏洞、product delta=0、production integration=0、真实 SEC/source admission/金融真值未资格化等边界均未被改写。

## 9. 2026-09-01 successor：最小前置已执行，不再停留在计划

Owner 随后授权按上述最小路径继续。统一 dependency source/lock、真实 PostgreSQL 16.15、thin Dagster S2 shadow、exact Workbench 与 image/native supply remediation 已分别在 S1/131 和 S1/132 真实实施并留证，不再是“下一步计划”。最新 exact clean commit=`e965f235e41b219e38ff8d01783fa5df4eeaf2e9`；两张 exact image、system-linked libpq、SBOM/raw/OpenVEX、fresh PostgreSQL/Dagster、exact control-plane real job、exact Workbench DELL/MU/NVDA readiness 和全仓 `2671 passed, 5 skipped` 已通过有界非生产资格，统一 summary SHA=`80f5121d...943b`。

这验证了本次成熟栈纠偏的核心方向：PostgreSQL、Dagster、uv、Syft、Grype 和 OpenVEX 可以通过薄适配接管通用工程责任，FIN domain kernel、旧回归与 authority 边界仍由项目保留，没有建设新的通用 scheduler、database、scanner 或计划执行 runtime。

但 production image/native supply 仍为 BLOCKED；它不能被非生产工程成功自动升级。剩余 7 Critical、residual High、Python/gzip/Debian处置、发布时最新数据库、license/legal、长期 Debian byte-reproducible source 和 production hardening 必须由 Owner 决定继续在 S5 处理，或先冻结当前可行性证据并转到全产品迁移路线的下一个已批准能力面。R14、R15/R16、formal、Evidence、current S2 authority、S3、report、product 和 release 仍未获得新权限。详见 `docs/worklog/fin_0_1_3_s1/132_image_native_supply_remediation.md`。
