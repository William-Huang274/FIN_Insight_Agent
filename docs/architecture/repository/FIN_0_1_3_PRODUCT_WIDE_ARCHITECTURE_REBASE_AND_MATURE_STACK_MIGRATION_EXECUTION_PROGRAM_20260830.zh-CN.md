# FIN 0.1.3 全产品架构重基线与成熟技术栈迁移执行程序

日期：2026-08-30  
程序 ID：FIN-0.1.3-PRODUCT-WIDE-ARCHITECTURE-REBASE-20260830  
计划合同版本：v1.0  
状态：PLAN CANDIDATE / OWNER 已授权先冻结本计划，再从 Phase 0 开始执行 / 尚未授权任何组件晋升  
当前分支：codex/fin013-dell-s1-s2-product-bridge  
计划起草基线：34589b6b8552e0236912dacb0664d7714bbf275c  
R14 implementation freeze：7e25cad95ee84b39fb2a51063100405bc27da6e5  

本文件是跨 S1–S5、跨数据面、控制面、产品面和仓库面的技术执行权威。它把此前口头说明的 Phase 0–7 变成可逐票执行、逐门验收、可停止、可回滚、可复审的工程程序。计划允许后续根据实测证据修订，但修订必须进入 Git、机器合同和工作记录，不得只依赖聊天记忆。

本文件本身不授权跳过前置门。计划冻结后，第一项实施仅为 Phase 0 治理重基线；组件下载、网络研究、模型调用、旧索引删除、代码迁移和产品切换分别受后续门约束。

## 1. Owner 决定与本程序解决的问题

Owner 已明确要求：

1. 不再沿 R14 继续扩写确定性开放英文语义系统；
2. 正确收口 R14，并过渡到一个新的全产品技术阶段；
3. 对 S1–S5、RAG、embedding、reranker、Agent、Evidence、S2、报告、Workbench、运维和安全做完整 Build / Adopt / Hold / Retire 审计；
4. 对应采用成熟栈的能力做广泛调研，而不是只列四五个知名项目；
5. 候选必须在本机或隔离环境真实下载、安装、固定版本并测试；
6. 旧代码、新成熟栈、当前必须补的适配/自研代码和未来接口必须形成清晰仓库结构；
7. 使用真实 case 验证完整产品链；允许在独立权限和预算合同下调用 DeepSeek API；
8. 最终交付必须是已集成、已验证、可回滚的可行架构，不是只写一份调研报告。

本程序把上述要求解释为一项新的“架构迁移程序”，不是新的产品版本、不是新的 S-stage，也不是 R15/R16。程序阶段使用 Phase 0–7，只描述迁移工作的成熟度；FIN 0.1.3、S0–S5、合同版本和执行 attempt 继续保持相互独立。

## 2. 当前事实基线与 R14 的准确收口

### 2.1 Git 与仓库基线

计划起草前已验证：

- canonical repository：D:\FIN_Insight_Agent；
- branch：codex/fin013-dell-s1-s2-product-bridge；
- HEAD 与 origin 同步：34589b6b8552e0236912dacb0664d7714bbf275c；
- 工作树无 tracked、staged 或未说明改动；
- R14 implementation freeze 仍为 7e25cad95ee84b39fb2a51063100405bc27da6e5。

计划冻结 commit 不能自我引用。Phase 0 的机器合同必须在 plan-only commit 之后绑定本文件的 exact commit、Git blob、文件 SHA-256 和字节数。

### 2.2 R14 不是 PASS，也不再是活动实现路线

唯一 R14 corpus parity preview 的不可变事实为：

- total cases：27,026；
- pass：26,787；
- fail：239；
- event-semantics failures：228；
- assertion-semantics failures：11；
- event mismatches：277；
- I2 governance：PASS，仅表示失败清单、输入、两类最早责任层、验收和停止条件已冻结；
- R14 product capability delta：none；
- R15/R16：不存在，也不得因本迁移程序创建。

R14 的程序处置定义为：

> active implementation strategically terminated / failed evidence preserved / regression baseline retained / no PASS / no root-cause erasure。

这意味着：

- 不再修改 R14 production implementation；
- 不进入 R14 pre-formal、policy 或 formal；
- 不用新框架或新模型把 R14 失败改写成成功；
- RC-S1-109 与 RC-S1-110 在 replacement 完整通过并由 Owner 作出同阶段责任处置前继续 open；
- 冻结 corpus、239 case、277 event mismatch、validator、旧输出和失败 receipt 继续作为 regression/adversarial evidence；
- 旧 parser 输出只能是 baseline，不能充当 human gold 或 truth oracle；
- replacement 的产品身份属于同一 S1 责任面，不使用 R15/R16 编号。

### 2.3 旧规划的权威变化

以下文档继续作为事实和约束输入，但不再单独决定下一步：

- R14 program-level architecture execution plan；
- R14 I2 governance closeout；
- FIN 0.1.3 current baseline and S0–S5 closeout plan；
- 产品 Build / Adopt / Hold / Retire 审计；
- 成熟技术栈 landscape decision packet；
- strict mainline rebaseline program。

Phase 0 必须在这些原文件中写入不破坏历史的 supersession / owner-decision note，并链接本程序。不能删除旧结论，也不能让旧文档继续显示“下一步是修改 R14”。

## 3. 身份轴、状态词和禁止混用

### 3.1 五条独立身份轴

| 身份轴 | 示例 | 用途 | 禁止误用 |
|---|---|---|---|
| 产品版本 | FIN 0.1.3 | 对用户承诺的一轮产品范围 | 不能给失败或迁移尝试编号 |
| S-stage | S1–S5 | 同一产品内的数据、研究、审阅、发布成熟度 | 不能替代产品版本 |
| 合同版本 | SemanticCandidate v1、SourceCapture v1 | schema、协议或行为变化 | 不能表示一次重跑 |
| 架构程序阶段 | Phase 0–7 | 本迁移程序的治理、审计、调研、资格、集成和收口 | 不能冒充 S-stage |
| execution/run/attempt | 日期＋能力＋候选＋split＋rN | 一次安装、测试、模型调用或迁移执行 | 失败不得自动创建产品/R编号 |

### 3.2 状态词

允许的程序状态为：

- planned；
- authorized；
- in_progress；
- passed；
- failed；
- stopped；
- blocked；
- superseded；
- regression_only；
- retired。

禁止使用含义不明的 done、ready、green 来代替验收结论。每个 passed 必须带 scope、证据和 known boundary。

### 3.3 决策标签

能力决策仅使用：

- KEEP_BUILD：FIN 必须拥有的金融权威或产品差异化；
- ADOPT_MATURE：成熟组件承担通用实现，FIN 保留薄 adapter 和业务合同；
- HOLD_TRIGGER：当前不进入主线，达到预声明触发条件再开；
- RETIRE_AFTER_PROOF：在 shadow、回滚和验收通过后退出活动主路径；
- REGRESSION_ONLY：只保留为历史、fixture、oracle attack 或对照；
- EXCLUDE：许可、安全、复杂度、锁定或能力边界不适合。

组件角色仅使用 default、challenger、managed ceiling、excluded。每类能力最终最多保留一个 default、一个 challenger 和一个 managed ceiling；选型结束后失败候选不进入正式依赖。

## 4. 全程序不可破坏的不变量

以下规则适用于 Phase 0–7，任何一项被破坏都必须停止当前 slice：

1. Candidate、Evidence、NumericFact、Research Judgment 和 Release Authority 永不合并。
2. 第三方输出只能进入其对应的未准入 envelope：
   - crawler/WARC → SourceCapture；
   - parser/OCR → ParsedElement、TableCell、Locator；
   - XBRL processor → unadmitted FactObservation；
   - retrieval/reranker → RetrievalCandidate；
   - LLM extraction/judge → SemanticCandidate；
   - 只有 FIN admission 才能产生 Evidence 或 NumericFact。
3. source identity、issuer、as-of、period、unit、scale、vintage、conflict、rights、citation eligibility、GapEligibility、financial bridge、WWC、人审和 release authority 由 FIN 持有。
4. 任何框架的 state、score、confidence、citation 或 grounded 标签都不自动获得 FIN 权威。
5. 旧失败和正式证据不可覆盖；修复或迁移使用新 attempt ID。
6. 失败留在最早责任层，不用 downstream fallback 掩盖。
7. 模型、Provider、付费 API 和真实外源动作必须有 task-specific TokenBudgetBasis。
8. 默认 SDK retry 为 0；不能在 FIN receipt 之外透明重试。
9. 未证明 external exactly-once 时，timeout/reset 必须写 unknown_external_completion 或 duplicate_risk 并停止。
10. 不可信网页、PDF、Office、图片、压缩包和 source-derived instruction 必须在解析、索引和模型前经过 MIME/magic、资源、malware、sandbox、egress/SSRF 与 prompt/tool/path/query injection 门。
11. frozen test/holdout 不用于调参；看到 hidden outcome 的实现上下文不得继续声称 blind。
12. 任何迁移都必须有 old path、new path、shadow/dual-read、rollback、exit 和 retire 条件。
13. 不为追求更便宜或更快静默删除必需研究工作。
14. 不把通用框架的安装成功、平均 benchmark 或 vendor claim 写成 FIN 产品通过。
15. MLflow、OTel、LangGraph、PostgreSQL、搜索引擎或任何第三方平台丢失，都不能改变 FIN 已签发的 Evidence 或 release 状态。

## 5. 目标架构原则与候选仓库结构

### 5.1 逻辑架构

~~~text
成熟数据与运行基础设施
  source/XBRL/crawl/WARC/document AI/storage/search/rerank
  provider SDK/workflow/checkpoint/trace/eval/render/security
                              |
                              | typed ports and thin adapters
                              v
FIN 金融权威内核
  identity/as-of/source role/rights
  Candidate/Evidence/NumericFact authority
  PIT/unit/period/vintage/conflict/financial bridge
  Gap/materiality/causal boundary/counter/WWC
  claim locator/human review/release/immutable receipt
                              |
                              v
FIN 产品应用
  Evidence Workspace / Workpaper / Review / Repair / Approval / Deliverable
~~~

### 5.2 候选代码结构

以下是 Phase 4 前的候选目标，不授权 Phase 0 立即批量移动文件。Phase 1 import/consumer 审计和 Phase 3 spike 可能修正命名，但职责分层不得反向合并。

~~~text
src/finsight/
  domain/
    identity/
    source_authority/
    evidence/
    numeric_facts/
    financial_bridge/
    research_quality/
    review_release/
  application/
    research_case/
    evidence_workflow/
    research_workflow/
    report_workflow/
  ports/
    capture.py
    document.py
    xbrl.py
    retrieval.py
    ranking.py
    semantic.py
    workflow.py
    provider.py
    telemetry.py
    artifact_store.py
    renderer.py
  adapters/
    capture/
    document/
    xbrl/
    retrieval/
    ranking/
    semantic/
    workflow/
    provider/
    telemetry/
    storage/
    rendering/
  platform/
    contracts/
    receipts/
    security/
    configuration/
  legacy_bridge/
    retrieval_r3_r14/
    research_runtime/
    provider_transport/

apps/workbench/
  backend/
  frontend/

scripts/
  qualification/
  migration/
  operations/

configs/
  repository/
  qualification/
  deployments/
  audits/

tests/
  contract/
  regression/
  qualification/
  integration/
  product/
  security/
~~~

### 5.3 与当前代码的过渡关系

| 当前区域 | Phase 1 初始假设 | 目标关系 |
|---|---|---|
| src/evidence | KEEP_BUILD | 迁入 domain/evidence，保持兼容 import |
| src/financial_facts | KEEP_BUILD | 迁入 domain/numeric_facts，先双读后切换 |
| identity/as-of/source role 分散实现 | KEEP_BUILD + consolidate | 收敛为一个 domain contract source |
| src/connectors、src/ingestion | WRAP/REPLACE | 成熟 source/document adapters，保留 FIN source authority |
| src/indexing、src/retrieval | WRAP/REPLACE/PARTIAL KEEP | 通用 index/search/rerank 由成熟栈承担；FIN query constraints 与 admission 保留 |
| src/sec_agent/providers | REPLACE | 官方 SDK＋薄 capability/receipt adapter |
| src/sec_agent/research | SPLIT | 金融方法和 domain state 保留；通用 orchestration/session/trace 迁出 |
| project_os_preflight.py | SHRINK | 跨版本不变量保留；attempt-specific 分支数据化/退役 |
| R3–R14 modules | REGRESSION_ONLY | 冻结、可重放，不进入新生产主路径 |
| apps/workbench | KEEP_PRODUCT + THIN | 留金融 Evidence/Gap/Review/Release；通用 trace/run UI 交成熟平台 |

任何真实目录移动必须等 Phase 4 ADR 冻结，并在 Phase 5 通过 compatibility shim、import map、consumer tests 和 rollback slice 完成。

## 6. 程序拓扑、提交拓扑与变更控制

### 6.1 程序依赖

~~~text
Plan-only commit C0
        |
        v fresh read-only plan review
Phase 0 governance authority G0
        |
        v
Phase 1 capability/import/data/consumer migration inventory
        |
        +----------------------+
        |                      |
        v                      v
Phase 2 broad research     frozen benchmark/gold/security fixture preparation
        |                      |
        +----------+-----------+
                   v
Phase 3 isolated qualification lab
                   |
                   v
Phase 4 target architecture and migration ADR freeze
                   |
                   v
Phase 5 release-sliced integration and compatibility migration
                   |
                   v
Phase 6 S1–S5 real-case acceptance
                   |
                   v
Phase 7 closeout, retirement and release recommendation
~~~

Phase 1 与 Phase 2 可在 Phase 0 后并行，但 Phase 3 只能消费二者冻结的输入。Phase 5 不能在 Phase 4 ADR 前开始。Phase 6 不能用尚未通过 Phase 5 slice gate 的组件。Phase 7 不能删除或退休仍被活动 consumer 使用的旧代码。

### 6.2 提交拓扑

1. C0：只包含本执行程序。
2. C0-review：fresh、作者分离、只读 reviewer 返回结构化 verdict；reviewer 不写仓库。
3. G0：Phase 0 authority commit，绑定 C0 commit/tree/blob/SHA/bytes；可包含一个机器程序合同、必要 source-doc supersession、Project OS、checklist、worklog 和定向测试。
4. 后续每个 release slice 独立提交：contract → implementation → frozen result → fresh review。失败 slice 不覆盖。
5. 大型组件安装和 run artifact 不进 Git；Git 只保存 lock、manifest、digest、license/SBOM 结论、测试代码和有界结果。
6. 不为每个小状态创建独立 authority 文件。维护一个 canonical current program manifest；材料 phase transition 或失败才创建 append-only audit receipt。

### 6.3 计划修订

本计划可修正，但需同时满足：

- 新证据写入 issue/capability ledger；
- 说明原假设、证据、影响、选择与 rollback；
- 计划合同版本仅在行为/门/接口变化时递增；
- 纯运行重试只增加 rN，不增加合同版本；
- 涉及产品范围、发布含义、付费规模、安全或不可逆动作时再次向 Owner 报告；
- 已完成/失败的历史证据不回写。

## 7. Phase 0：R14 终止与新架构治理重基线

### 7.1 目标

把 Owner 决定变成仓库可恢复、机器可检查的唯一当前权威；明确 R14、旧计划、新程序和所有下游权限。

### 7.2 非目标

- 不修改任何 R14 implementation/test/frozen corpus/failure receipt；
- 不安装候选；
- 不调用网络、模型、Provider、外源、embedding 或 reranker；
- 不改 Evidence、S2、S3、报告或产品行为；
- 不删除 D:\FIN_Insight_Agent\data\indexes。

### 7.3 需求票

| Ticket | 输入 | 输出 | 验收 |
|---|---|---|---|
| P0-01 plan freeze | 本文件 C0 | exact plan commit/blob/SHA/bytes | fresh reviewer P0/P1/P2=0/0/0 |
| P0-02 R14 strategic disposition | R14 freeze、I2、RC-S1-109/110、Owner 决定 | R14 active=false、regression=true、PASS=false、R15/R16=false | old failure/count/digest不变 |
| P0-03 program authority | C0 identity、phase matrix、deny set | configs/repository/fin_0_1_3_product_wide_architecture_rebase_execution_program_v1_0.json | JSON/semantic test pass |
| P0-04 source supersession | 产品审计、成熟栈包、R14 plan/I2、baseline docs | 原位 owner-decision/supersession notes | 不改写历史结论 |
| P0-05 Project OS | capability/root-cause/current context/checklist/README | append-only current state | JSONL parse、current context一致 |
| P0-06 governance test | machine authority 与 C0 Git binding | tests/test_product_wide_architecture_rebase_program.py | exact Git blob/SHA、authority/deny/index boundary pass |
| P0-07 worklog | 所有变更、命令、未执行项 | docs/worklog/product_wide_architecture_rebase/130_phase0_program_blueprint_and_authority.md | factual、可恢复 |

### 7.4 Phase 0 机器合同最低字段

- schema_version、program_id、contract_version、status；
- owner_decision_at、owner_decision_summary；
- canonical_branch、authority_commit_parent、plan path/commit/tree/blob/SHA/bytes；
- product_version、S-stage status、R14 implementation freeze；
- R14 disposition、failure counts、open root causes；
- current phase、phase sequence、phase transition rules；
- current allowed actions、explicit denied actions；
- component promotion、model、network、paid、external、Evidence、S2/S3/report/release booleans；
- data/index destructive boundary；
- source docs、ledgers、review receipt；
- change control、stop conditions、known boundary。

### 7.5 Phase 0 退出门

- plan fresh review 无 P0/P1/P2；
- machine config 与 exact plan commit 一致；
- R14 在所有 current source 中均为 strategic termination / not PASS；
- RC-S1-109/110 仍 open；
- RC-S0-111 进入 owner-authorized architecture rebase active；
- no R15/R16；
- no component/model/network/migration/delete authority 被意外打开；
- targeted tests、JSON/JSONL parse、diff check、Git clean；
- commit 与 non-force push 成功。

失败时只修 Phase 0，不进入 Phase 1。

## 8. Phase 1：全产品能力与旧代码迁移审计

### 8.1 目标

从真实 import、consumer、data、artifact 和运行入口出发，建立每个能力的 retain/wrap/replace/regression/retire 决策；识别真正的 FIN domain kernel 和通用轮子。

### 8.2 固定输入

- Phase 0 exact authority；
- current active baseline manifest；
- current code map 和 strict mainline gates；
- pyproject/requirements/lockfiles；
- src、apps、scripts、configs、tests、data contracts；
- Runtime registry、Workbench composition root；
- R14/R17/Project OS frozen evidence；
- current local data/artifact roots，仅做路径、schema、consumer 和容量审计，不读取 hidden outcome。

### 8.3 需求票

| Ticket | 工作内容 | 主要输出 |
|---|---|---|
| P1-01 active import graph | Python、frontend、runtime resource、CLI/API/worker entrypoints | active_consumer_graph_v1 |
| P1-02 capability inventory | S1–S5、data/control/product/security/ops 全能力 | product_capability_inventory_v1 |
| P1-03 domain-kernel extraction | identity/source/Evidence/Numeric/PIT/bridge/Gap/WWC/release | fin_domain_kernel_map_v1 |
| P1-04 legacy R-chain audit | R3–R14 files、tests、fixtures、current consumers、historical-only paths | r_chain_legacy_disposition_v1 |
| P1-05 artifact/data map | raw/source/object/index/SQL/model/trace/eval/report/private/public | artifact_lineage_and_rebuild_map_v1 |
| P1-06 contract map | schemas、IDs、failure codes、receipts、API/UI surfaces | canonical_contract_gap_map_v1 |
| P1-07 dependency/license map | direct/transitive deps、duplicate capability、platform constraints | dependency_and_license_baseline_v1 |
| P1-08 migration matrix | retain/wrap/replace/regression/retire，owner、consumer、risk、rollback | capability_migration_matrix_v1 |
| P1-09 acceptance fixture map | current fixtures、blind restrictions、missing gold、real-case needs | qualification_input_readiness_v1 |

### 8.4 每个模块必须回答

- 谁 import/调用/展示它；
- 输入、输出、schema、side effect 和 data root；
- 是否持有 FIN 权威；
- 是否可由成熟组件替代；
- replacement port 是什么；
- 哪些 tests 是 truth、regression、implementation-coupled 或已污染；
- shadow/dual-read 怎么做；
- rollback 怎么做；
- retire 前最后一个 consumer 是谁；
- 删除后如何恢复；
- 许可证、隐私、部署和资源限制。

### 8.5 Phase 1 输出路径

- docs/architecture/repository/FIN_0_1_3_PRODUCT_CAPABILITY_AND_LEGACY_MIGRATION_INVENTORY_20260830.zh-CN.md；
- configs/repository/fin_0_1_3_product_capability_migration_matrix_v1_0.json；
- configs/repository/fin_0_1_3_active_consumer_and_artifact_rebuild_map_v1_0.json；
- 对现有 code map 的增量 supersession note；
- Phase 1 worklog 和 fresh read-only review receipt。

### 8.6 退出门与停止条件

通过要求：

- S1–S5 每个产品能力都有 owner 和 decision；
- 所有活动 import/consumer 都有归属；
- 所有大 artifact 都有 producer、input、rebuild、consumer、retention；
- R3–R14 不再被误标为多个活动产品版本；
- domain kernel 不依赖具体 vendor schema；
- migration matrix 可以逐模块执行和回滚。

停止：

- 无法证明某模块是否被活动消费者使用；
- hidden/holdout 边界不清；
- data artifact 没有可重建输入；
- 计划要求先删除再理解；
- 为迁移方便需要放宽 Evidence/Numeric/release 权威。

## 9. Phase 2：成熟技术栈广泛调研与 shortlist 冻结

### 9.1 目标

在每个 ADOPT_MATURE 能力面建立足够广、足够新、又有现实采用证据的 longlist；形成可测试 shortlist，而不是直接把知名度当答案。

### 9.2 调研工作流

每个 capability family 必须执行：

1. 定义问题、FIN-specific constraints 和非目标；
2. 发现 longlist；
3. 只用官方 docs/repo/spec/paper 核实能力、版本、许可和限制；
4. 用 release cadence、issue/security posture、维护者、现实部署案例和生态兼容性判断成熟度；
5. 记录 native Windows、WSL2、Docker Linux、remote Linux、managed 画像；
6. 记录 data region、retention、training/use-of-data、pricing 和 exit；
7. 明确排除理由；
8. 选 default candidate、challenger、managed ceiling；
9. 冻结 exact version/tag/commit/model revision 候选；
10. 由未参与调研结论编写者做 evidence review。

### 9.3 必须覆盖的技术面

1. regulator/issuer official APIs 与 XBRL；
2. HTTP/crawl/browser/WARC/source capture；
3. untrusted-content intake security；
4. PDF/OCR/layout/table/chunk/document intelligence；
5. canonical metadata、transaction、object/artifact、Parquet/analytics；
6. lexical/vector/hybrid search；
7. embedding 与 reranker；
8. source-grounded LLM semantic extraction、span alignment、abstain/human；
9. Agent state/checkpoint/HITL 与 durable jobs；
10. Provider SDK、structured output、gateway、MCP；
11. OTel/trace/eval/experiment/artifact lineage；
12. schema/preflight/policy/IAM/secrets；
13. human annotation/review/citation/report rendering；
14. GraphRAG 与 whole-RAG platform，只作触发式/benchmark 判断；
15. Workbench product UX 与 operator UX 的职责分离。

### 9.4 调研饱和标准

不能用“列了几个 famous 项目”收口。每个 family 至少满足：

- 已覆盖一条成熟本地/OSS 路线；
- 已覆盖一个不同架构的现实 challenger；
- 有商业价值时覆盖一个 managed ceiling；
- 对明显相关的近期/广泛采用候选有 include/exclude 记录；
- 连续两轮发现检索没有出现新的能力类别或会改变 shortlist 的候选；
- 所有排除项都对应许可、能力、维护、部署、隐私、成本、锁定或 FIN gate；
- 仍存在信息时效不确定时明确标记并进入 Phase 3 exact snapshot，不假装已固定。

若某 family 现实上不足三个可信候选，可以少于三个，但必须说明市场结构和为何继续搜索不会改变决策。

### 9.5 shortlist 不是 winner

当前 landscape packet 中的 SEC+Arelle、Scrapy+Playwright+warcio、Docling、MinerU、PostgreSQL+Parquet+DuckDB、pgvector/OpenSearch、BGE/Cohere、LangExtract+DeepSeek、LangGraph、official OpenAI SDK、Pydantic、OTel/OpenInference、MLflow、Quarto/Pandoc/CSL 只是 Phase 2 seed hypothesis。任何一项未经 Phase 3 exact qualification 都不能写成正式已采用组件。

### 9.6 输出与退出门

输出：

- product-wide landscape v2；
- candidate registry；
- exact source/version/license snapshot；
- shortlist/exclusion matrix；
- qualification hypotheses、metrics 和 resource estimates；
- research saturation receipt。

退出要求：

- 每个 ADOPT 能力有至少一个可运行 shortlist；
- 每个 shortlist 有 exact qualification profile；
- 没有许可/隐私/部署 blocker 被藏在“后续再看”；
- Phase 3 所需下载、磁盘、GPU、API、服务和 fixture 预算可计算；
- fresh reviewer 对事实引用与 recommendation 分离给 PASS。

## 10. Phase 3：Z 盘 qualification lab 与组件实测

### 10.1 实验室根与隔离

建议主根：

Z:\FIN_Insight_Agent_qualification_lab\20260830_product_wide_architecture_rebase_v1

建议结构：

~~~text
downloads/
sources/
envs/
models/
services/
images/
fixtures/
corpora/
indexes/
runs/
artifacts/
licenses/
sbom/
logs/
quarantine/
~~~

大文件、虚拟环境、模型、容器层、候选源码和运行产物不进 Git。仓库只保存：

- qualification manifest；
- lockfile/revision/digest；
- fixture manifest；
- commands；
- bounded metrics/result；
- license/SBOM conclusion；
- failure/stop receipt；
- winner/challenger decision。

### 10.2 每个 candidate 的固定 manifest

- candidate family/name/role；
- exact version/tag/commit/package hash；
- source URL、access time、source/license digest；
- Python/Java/Node/runtime/OS；
- native Windows/WSL2/Docker/remote/managed profile；
- container image digest；
- model repo/revision/weights/tokenizer digest；
- CUDA/driver/hardware；
- config/schema/prompt digest；
- fixture/corpus/query/gold digest；
- network domains、ports、egress；
- secrets and privacy class；
- estimated and actual disk/RAM/VRAM；
- start/stop/recovery/backup/export/uninstall；
- transitive SBOM/license；
- hypothesis、baseline、ceiling、metrics、stop；
- run IDs 与 artifacts；
- decision：pass/fail/hold/winner/challenger/ceiling。

### 10.3 先零调用，再真实调用

顺序固定：

1. install/import/version/license smoke；
2. saved/synthetic fixture compatibility；
3. failure injection、timeout、malformed、security；
4. frozen local corpus benchmark；
5. 只有前四项通过，才进入允许的外部/managed/model shadow；
6. live run 后必须重新做 deterministic post-validation 和 author-separated review。

### 10.4 首轮资格切片

每项独立 ticket、独立变量，不做十项大爆炸：

| Slice | default/challenger | 核心 gate |
|---|---|---|
| QL-01 contracts | Pydantic strict canonical source | old/new schema parity、unknown field、cross-field FIN invariant |
| QL-02 intake security | MIME/magic + malware + sandbox + egress | zip bomb、SSRF、active content、prompt/tool/path/query injection |
| QL-03 source/XBRL | SEC API + Arelle | accession/period/unit/dimension/amendment/raw lineage |
| QL-04 capture/WARC | Scrapy + Playwright + warcio | redirect/resume/rate/raw round-trip/as-of |
| QL-05 document | Docling vs MinerU + one managed ceiling if approved | page/bbox/cell/span/footnote/cross-page table |
| QL-06 storage | PostgreSQL + Parquet + DuckDB | transaction/PITR/snapshot/rebuild/locking |
| QL-07 retrieval | PostgreSQL+pgvector vs OpenSearch | identifier/period/unit/source-role/PIT/Recall/MRR/nDCG/p95/rebuild |
| QL-08 rerank | BGE v2-m3 vs managed ceiling | target-in-pool first、material slice、latency/resource |
| QL-09 semantic | LangExtract pattern + DeepSeek shadow | exact span/schema/hard validator/abstain/human gold |
| QL-10 workflow/provider | LangGraph + official SDK | max_retries=0、checkpoint、HITL、duplicate-risk、crash recovery |
| QL-11 trace/eval | OTel/OpenInference + MLflow | passive import、privacy、export、authority independence |
| QL-12 rendering | Quarto/Pandoc/CSL | claim/citation precheck、PDF/DOCX/HTML visual parity |

### 10.5 DeepSeek API 使用合同

Owner 已允许真实 case 中使用 DeepSeek API，但每个节点仍须在调用前创建 TokenBudgetBasis，至少包含：

- node purpose；
- input scale 和 source/privacy class；
- required outputs；
- schema burden；
- materiality/quality risk；
- comparable run evidence；
- model/deployment/profile/reasoning mode；
- max input/output/reasoning budget；
- stop/truncation behavior；
- expected cost/latency；
- retry policy，默认 max_retries=0；
- request hash、idempotency key、wire ordinal、start/terminal receipt；
- API key 仅来自环境/secret store，不进日志或 artifact。

Semantic shadow 只能产生 SemanticCandidate。模型不能写 Evidence、NumericFact、Gap closure、S2 bridge 或 release verdict。旧 R14 parser output 不作 truth；case-correct human-adjudicated gold 才是主判定。

### 10.6 D 盘 data\indexes 条件式清理授权

Owner 已明确授权：如果成熟技术栈测试确需 D 盘空间，可以严格移除 D:\FIN_Insight_Agent\data\indexes 下的文件，并接受旧 retrieval 暂停、之后按新架构重建。

该授权不是立即删除。触发条件全部满足后才可执行：

1. Z 盘作为主 lab，已先尝试按 candidate 分批、释放失败候选和避免同时保留重复环境；
2. exact qualification storage budget 已计算：
   required = download + unpack + env/image + model + corpus copy + index + run artifacts + rollback/export + 20% headroom；
3. 保持 Z 盘安全余量后仍无法完成已批准 candidate；
4. 证明把工作转到 D 盘并清理 index subtree 后可以满足预算；
5. data\indexes 当前无活动 writer/reader/job/service；
6. 已生成并提交 index retirement manifest；
7. 已冻结 retrieval suspension 状态和 rebuild acceptance；
8. 已向 Owner 在执行更新中报告将触发该授权。

删除前 manifest 至少记录：

- exact root resolved path；
- relative path、type、size、mtime、SHA-256 或对超大文件预声明的流式 digest；
- total file/dir/bytes；
- producer command/config/commit；
- input raw/source/object/corpus digests；
- active consumers；
- old query/index contract；
- known non-reproducible items；
- rebuild command、target new adapter、acceptance；
- before-free-space 和预计释放。

删除边界：

- 只允许删除 D:\FIN_Insight_Agent\data\indexes 的后代内容；
- 保留并重新创建空的 data\indexes 根；
- D:\FIN_Insight_Agent\data\staging 不在范围；
- data\processed_private、raw/source/object、workbench_private、eval/report、R14 evidence、Codex live state 均不在范围；
- 即使存在同名 staging，只有位于 data\indexes 内的后代才属于本授权；
- 必须在一个 PowerShell 流程中解析、验证全部 absolute target，再逐项 Remove-Item -LiteralPath；
- 禁止 glob、环境变量拼接、跨 shell 删除和 broad recursive target。

删除后：

- 记录实际删除项、释放空间和是否可恢复；
- old retrieval status=temporarily_suspended_for_architecture_rebuild；
- 所有依赖旧 index 的命令/API/UI 必须 fail visibly，不能静默返回空结果或 public gap；
- 新 retrieval 只有通过 input digest、row/object count、identifier zero-miss、query suite、known regression、lineage、rebuild、backup/restore 和 fresh review 后才可恢复 active。

### 10.7 Phase 3 退出门

- 每类能力有 winner/challenger/ceiling 或有证据的 hold/exclude；
- exact versions、locks、SBOM/license、deployment profile、backup/export 已固定；
- frozen benchmark 和失败 artifacts 完整；
- critical FIN slices 无未解释退化；
- model/managed runs 有 TokenBudgetBasis 和 receipt；
- 资源、成本、隐私、安全、退出结论完整；
- fresh reviewer 可独立复算主要指标；
- 失败 candidate 未进入正式 requirements/compose/mainline。

## 11. Phase 4：目标架构与迁移方案冻结

### 11.1 目标

只根据 Phase 1 真实依赖和 Phase 3 实测 winner 冻结目标架构；把候选目录结构转为 ADR、ports、data contracts、deployment profiles 和 migration waves。

### 11.2 必须形成的 ADR

1. FIN domain kernel boundary；
2. canonical envelopes 与 Pydantic contract source；
3. source/XBRL/document adapters；
4. metadata/artifact/storage；
5. retrieval/ranking primary；
6. semantic candidate/human escalation；
7. Agent state/provider/external side-effect receipt；
8. observability/eval authority separation；
9. Workbench review/product boundary；
10. report/citation/render；
11. security/privacy/IAM trigger；
12. legacy bridge/retirement；
13. deployment profiles；
14. backup/restore/rollback/exit。

### 11.3 每个 port 的最低合同

- request/response schema；
- domain ID 与 vendor ID 映射；
- allowed side effects；
- timeout/retry/idempotency；
- artifact/receipt；
- privacy/security；
- error taxonomy；
- observability fields；
- test fixture；
- fallback 是否属于产品行为；
- rollback；
- deprecation。

### 11.4 迁移波次冻结

| Wave | 内容 | 前置 | 回滚 |
|---|---|---|---|
| W0 | namespace/ports/contracts scaffold，不改产品结果 | Phase 4 ADR | 删除新未消费 scaffold |
| W1 | passive trace/experiment/contract validation | QL-01/11 | 关闭 exporter，FIN artifact 不变 |
| W2 | source/XBRL/document intake adapters | QL-02/03/04/05 | route 回旧 capture，保留 shadow artifact |
| W3 | metadata/storage/retrieval/ranking | QL-06/07/08 | dual-read 回旧 index snapshot |
| W4 | semantic/provider/workflow | QL-09/10 | semantic shadow off，旧 product route不变 |
| W5 | report/render/review UX | QL-12 + Workbench contract | 回旧 renderer/read surface |
| W6 | consumer cutover 与 legacy regression-only | Phase 6 slice pass | compatibility shim re-enable |

Phase 4 退出前禁止批量移动当前模块、删除旧代码或更换产品主路由。

## 12. Phase 5：当前分支实际集成与仓库整理

### 12.1 实施原则

- 先 port/adapter，再 consumer；
- 先 shadow/dual-read，再 cutover；
- 不对同一 authority 双写；
- 每个 slice 可独立 review/test/rollback；
- 不把失败候选加入正式 dependency；
- 不同时改变 data source、parser、retriever、reranker、semantic judge 和 product acceptance；
- legacy bridge 必须有 removal condition，不得成为永久第二架构。

### 12.2 每个 integration slice

必须包含：

- problem/user value；
- inputs/outputs/non-goals；
- affected contracts/API/UI/data；
- exact dependency/version；
- implementation and compatibility files；
- migration/read/write route；
- feature/config switch；
- deterministic/unit/integration/product tests；
- data migration/rebuild；
- security/privacy；
- observability；
- rollback；
- known gaps；
- fresh reviewer verdict。

### 12.3 依赖与配置治理

- pyproject 只加入胜出且被当前 slice 消费的 dependencies；
- large-model/optional stacks 分 optional profile；
- lockfile、image digest、model revision 和 browser/runtime version 固定；
- compose 只包含正式 profile；
- qualification-only service 不进入默认 startup；
- secrets 只用 env/secret store；
- no-data、partial-data、service-down 和 rollback 路径都 fail visibly。

### 12.4 旧代码处置

每个旧模块只能进入：

- active compatibility；
- shadow comparison；
- regression fixture；
- archived/retired。

retire 前必须：

- active consumer=0；
- import/runtime registry=0；
- equivalent/new product path passed；
- rollback snapshot 可恢复；
- docs/redirect map 更新；
- historical failure/evidence preserved；
- fresh audit。

## 13. Phase 6：真实 case 与 S1–S5 产品验收

### 13.1 case 设计

至少覆盖：

- DELL、MU、NVDA 当前案例；
- 多个未用于实现调参的异质公司；
- 10-K、10-Q、8-K、earnings transcript、IR HTML/PDF、产品页、客户/供应商/监管来源；
- digital-native、扫描、双栏、复杂表、跨页表、脚注、重述、冲突；
- exact identifier、period、unit、scale、amendment；
- counterevidence、hard negative、source role、rights；
- malicious/malformed intake fixture；
- source absent、object failure、index failure、provider failure、human defer 等负路径。

开发、valid temporal、frozen test 和 external holdout 分离；test 结果不能反向调 threshold/route/model。

### 13.2 S1–S5 验收链

~~~text
S1 source/capture/parse/object/index/retrieval/rank
   -> CandidateDecision / Evidence admission / GapEligibility
S2 NumericFact / PIT / unit-period-vintage-conflict / financial bridge
S3 research plan / evidence-bound judgment / counter / WWC / report model
S4 review / repair / approval / reader citation / source appendix
S5 product, operations, security, rollback and release decision
~~~

每一阶段独立通过；后序 PASS 不能抵消前序失败。

### 13.3 质量门

S1：

- source/capture/object/index route receipts；
- identifier zero-miss；
- target-in-pool；
- Recall@k/MRR/nDCG 与 material slices；
- exact locator；
- Candidate 不冒充 Evidence；
- genuine gap 只有在本地/可达路线穷尽后。

S2：

- entity/period/unit/scale/dimension/vintage/conflict；
- XBRL 与 visual channel 冲突显式；
- units/share → ASP/mix → PVM → product profit → working capital；
- 输入不足时 null/gap，不伪造。

S3：

- 每个模型节点独立 TokenBudgetBasis；
- strict schema、visible source authority、hard validator；
- counterevidence、causal boundary、materiality、WWC；
- no ungrounded numeric or hidden authority borrowing；
- interrupted/timeout/duplicate-risk 可恢复。

S4：

- admit/reject/rebind/defer/reopen；
- author-separated review；
- claim→passage/page/table/cell；
- reader-visible title/issuer/date/period/locator/URL；
- source appendix；
- repair 不覆盖原失败。

S5：

- end-user workflow solves the task；
- latency/cost/resource；
- backup/restore/upgrade/rollback；
- security/privacy/license/IAM profile；
- accessibility、desktop/mobile、no-data/service-down；
- human product acceptance；
- publication/release 独立决定。

### 13.4 failure injection

必须覆盖：

- source/network timeout、partial、redirect；
- parser crash/timeout/resource；
- database/index unavailable/corrupt；
- provider complete 后 receipt 前崩溃；
- checkpoint 前后崩溃、duplicate resume；
- malformed/empty/truncated schema；
- human deny/defer/timeout；
- telemetry backend unavailable；
- renderer failure；
- rollback and rebuild。

任何未知 completion、duplicate risk、data drift 或 authority mismatch 必须 fail closed。

### 13.5 Phase 6 退出门

- 关键金融 slice 无未解释 P0/P1；
- deterministic、model、human 三层结果分开；
- DeepSeek 真实 case 不是 self-judge 唯一标准；
- qualified-human Evidence 和 product review 完成；
- cost/latency/resource/security/operations 可接受；
- old/new comparison 与 rollback 演练通过；
- S1–S5 各自 verdict 明确；
- 不通过弱化 validator、删 case 或隐藏失败得到 PASS。

## 14. Phase 7：迁移收口与最终可行性方案

### 14.1 收口工作

1. 正式 default/challenger/managed ceiling 清单；
2. 清理失败/未消费实验 dependency、service 和 image；
3. legacy code 转 compatibility/regression/retired；
4. 完成 archive/redirect/import/runtime consumer map；
5. 固定 lock、SBOM、license、security、deployment；
6. 备份/恢复/升级/rollback/exit runbook；
7. 运维、监控、成本和容量计划；
8. 最终 architecture、feasibility、migration、operations 文档；
9. Project OS、worklog、README、checklist、public docs 一致；
10. clean branch、exact staging、commit、non-force push；
11. fresh engineering/Evidence/report/product/security review；
12. Owner 决定产品版本和 release，不由程序自动推断。

### 14.2 完成定义

本程序只有在以下全部成立时才 complete：

- R14 已正确 strategic close，未假装 PASS；
- 旧规划已被当前程序和 ADR 正确 supersede；
- S1–S5 每个能力有 Build/Adopt/Hold/Retire；
- Adopt 能力有广泛 longlist、排除记录和 research saturation；
- 胜出组件已实际安装、固定版本、SBOM/license 和部署画像；
- Z 盘 lab 可复现；
- 当前分支已按目标架构集成；
- FIN domain kernel 与 vendor/framework 隔离；
- 旧代码有兼容、回归、退役和 rollback；
- 真实 case 和 DeepSeek 允许节点已验证；
- critical financial slice 无未解释重大错误；
- S1–S5、人审、报告、产品、运维、安全分别有 verdict；
- 没有隐藏失败、削弱 validator 或用 vendor benchmark 替代产品证明；
- Git/Project OS clean、同步、可恢复。

若某组件或产品门失败，可以形成部分可行性结论和 stopped/hold 决策，但不能把全程序标成 complete。

## 15. 跨阶段质量、测试与证据等级

### 15.1 测试层级

| Level | 内容 | 何时运行 |
|---|---|---|
| T0 | compile、JSON/schema、changed-file static、diff | 每次小改 |
| T1 | ticket direct unit/contract/security fixture | 每张票 |
| T2 | adjacent adapter/consumer/regression | 每个 slice |
| T3 | phase integration、frozen benchmark/rebuild/recovery | phase freeze |
| T4 | full repository、frontend/build/browser/secret | shared surface 或 phase close |
| T5 | real-case S1–S5、model/human/product/operations | Phase 6 |

高风险迁移不得仅用 T0/T1。全仓也不应在每次小改重复运行；trigger 和超时写入 ticket。

### 15.2 证据等级

- L0：文档/计划；
- L1：schema/fixture；
- L2：本地组件；
- L3：相邻 integration；
- L4：真实 frozen case；
- L5：独立 review/human/product；
- L6：release/operations。

安装成功最高只能证明 L1/L2；真实 case 没有人审不能自动到 L5。

### 15.3 评审分离

- 计划作者不能签自己的 final plan review；
- 组件实施者不能单独签 winner；
- 模型输出不能自评为 release；
- reviewer 默认只读；
- qualified-human 只在明确授权的 Evidence/product gate 中签发；
- reviewer finding 必须按 P0/P1/P2/P3 和最早责任层记录。

## 16. 安全、隐私、许可和供应商退出

每个候选在下载/安装前回答：

- 官方 source 和 exact revision；
- core/model/data/license 是否允许当前及未来商业形态；
- 是否有 AGPL/SSPL/ELv2/NC/open-core/hosted 限制；
- transitive SBOM；
- CVE/security update 和维护状态；
- source data 是否离开本机；
- region、retention、training/use-of-data；
- log/trace 是否含 private content；
- egress/domain/port；
- credential scope/rotation；
- export、backup、delete、uninstall、vendor exit；
- Windows/WSL2/Docker/remote/managed 实际资格。

法律意见未完成时只能标 legal_review_pending，不能写 license pass。

## 17. 程序风险与预置应对

| 风险 | 早期信号 | 处置 |
|---|---|---|
| 引入框架后胶水更多 | 多套 state/schema/trace 并存 | 每类只保留一个 default；停止第二控制面 |
| vendor schema 渗透 | domain 层出现 vendor ID/score/state | 退回 port/adapter，禁止 consumer cutover |
| benchmark 追平均分 | critical period/unit/source slice 退化 | critical slice hard gate |
| LLM 变事实裁判 | model output 直接进入 Evidence | fail closed，恢复 SemanticCandidate 边界 |
| 迁移变量过多 | 一次同时换 parser/search/model/workflow | 拆 slice，单变量/可归因 |
| 磁盘再次不足 | lab budget 无 exact bytes | 停止下载；先分批或触发受控 index cleanup |
| 删除后无法重建 | index 无 input/producer digest | 禁止删除 |
| 旧代码永久桥接 | removal condition/consumer map 缺失 | 不允许切换完成 |
| 观测平台变权威 | MLflow/trace 状态影响 Evidence | 断开 authority，恢复 FIN manifest |
| 计划过度刚性 | 新证据明显推翻 shortlist | 走 change control，不机械执行 |

## 18. 当前 authority matrix

计划候选尚未冻结时：

| 动作 | 当前 |
|---|---:|
| 写作、审查本计划 | true |
| Phase 0 authority/source-doc/Project OS 更新 | plan fresh PASS 后 true |
| Phase 1 read-only audit | Phase 0 PASS 后 true |
| Phase 2 网络调研 | Phase 0 PASS 后按 research ticket true |
| package/repo/model 下载 | false，Phase 3 manifest 前不允许 |
| Z 盘 qualification install/run | false，Phase 3 entry gate 前不允许 |
| 删除 D:\FIN_Insight_Agent\data\indexes | false，Phase 3 条件全部满足后才允许 |
| R14 implementation/pre-formal/formal | false / permanently not on active route |
| R15/R16 | false |
| DeepSeek live | false，Phase 3/6 ticket + TokenBudgetBasis 后才允许 |
| external source execution | false，单独 route ticket 前不允许 |
| embedding/reranker | false，target-in-pool 与 qualification gate 前不允许 |
| Evidence/S2/S3/new report/product/release | false，按 Phase 6 顺序分别验收 |

## 19. 计划冻结后的第一执行队列

严格顺序：

1. fresh、作者分离、只读审查本 plan-only commit；
2. 修复所有 P0/P1/P2，必要时新 plan-only revision；
3. 提交并推送 exact plan；
4. 创建 Phase 0 machine authority，绑定 exact plan identity；
5. 原位更新 R14、产品审计、成熟栈包、Project OS、checklist 和 README；
6. 添加 Phase 0 machine-semantic test；
7. targeted verification、fresh Phase 0 review、commit/push；
8. 只在 Phase 0 PASS 后开始 Phase 1 read-only capability/import/data audit。

本队列不包含 package install、模型调用、外源、formal、索引删除或生产迁移。

## 20. Source index

- docs/product/FIN_0_1_3_PRODUCT_CAPABILITY_BUILD_ADOPT_HOLD_RETIRE_AUDIT_20260830.zh-CN.md
- docs/architecture/research/FIN_0_1_3_MATURE_TECH_STACK_LANDSCAPE_AND_ADOPTION_DECISION_PACKET_20260830.zh-CN.md
- docs/architecture/research/FIN_0_1_3_MATURE_STACK_RESEARCH_SNAPSHOT_MANIFEST_20260830.zh-CN.md
- docs/architecture/repository/FIN_0_1_3_CURRENT_BASELINE_CODE_MAP_20260811.zh-CN.md
- docs/architecture/repository/FIN_0_1_3_STRICT_MAINLINE_REBASELINE_ACCEPTANCE_AND_MIGRATION_PROGRAM_20260811.zh-CN.md
- docs/worklog/fin_0_1_3_s1/124_dell_03b_R14_program_level_architecture_execution_plan.md
- docs/worklog/fin_0_1_3_s1/128_dell_03b_R14_I2_corpus_parity_governance_correction_and_reaudit_pass.md
- docs/worklog/fin_0_1_3_s1/129_product_capability_audit_and_mature_stack_decision_packet.md
- docs/project_os/current_context_pack.zh-CN.md
- docs/project_os/capability_status_ledger.jsonl
- docs/project_os/root_cause_issue_ledger.jsonl
- docs/project_os/external_pattern_registry.jsonl
- docs/project_os/financial_research_method_registry.jsonl
