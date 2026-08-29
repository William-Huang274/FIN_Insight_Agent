# FIN 0.1.3 全产品架构重基线与成熟技术栈迁移执行程序

日期：2026-08-30

程序 ID：FIN-0.1.3-PRODUCT-WIDE-ARCHITECTURE-REBASE-20260830

计划合同版本：v1.4

状态：REVISION CANDIDATE / exact v1.3 commit `b1c961ed...` author-separated read-only review=`PLAN_FAIL 0/1/1/0` / OWNER 已授权先冻结本计划，再从 Phase 0 开始执行 / 尚未授权任何组件晋升

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

### 3.2 状态轴与唯一 machine vocabulary

机器合同不得使用一个通用 `status` 混装阶段、票据、动作、证据和程序收口。唯一允许的原始状态轴如下：

| 轴/字段 | 允许值 | 语义 |
|---|---|---|
| `phase_status` | `planned / candidate / in_progress / passed / failed / stopped / blocked / superseded` | Phase 0–7 的阶段状态 |
| `phase_review_status` | `not_started / pending / passed / failed` | 对当前 phase candidate/result 的独立 review 状态 |
| `ticket_lifecycle_stage` | `planned / candidate / candidate_reviewed / execution_authorized / result_frozen / result_reviewed / terminal` | 单票从事前合同到不可变结果的生命周期 |
| `ticket_terminal_status` | `null / passed / failed / stopped / held / superseded` | 仅当 lifecycle=`terminal` 时才允许非 null |
| `downstream_activation_status` | `not_applicable / pending / activated / denied / revoked` | terminal PASS 后是否已独立激活下游消费或下一阶段 |
| `action_grant_status` | `not_granted / authorized / active / consumed / expired / revoked` | 某个 exact action 当前是否可执行；同时必须有 `granted:boolean` |
| `program_terminal_status` | `null / complete / partial / stopped / failed` | 整个 Phase 0–7 程序的最终状态，非 phase/ticket 状态 |
| `artifact_immutability` | `mutable_candidate / frozen_immutable` | manifest/result/corpus/receipt 的证据属性，`frozen` 不是 phase 状态 |
| `implementation_lifecycle` | `current / shadow / compatibility / regression_only / retired` | 代码/组件实现所处产品生命周期，非程序状态 |

有执行动作的 ticket 必须按 `planned → candidate → candidate_reviewed → execution_authorized → result_frozen → result_reviewed → terminal` 前进；`execution_authorized` 必须有独立 `execution_authority_receipt`，它发生在动作和结果之前。无执行动作的只读/聚合 ticket 可以不经过 `execution_authorized`，但必须显式写 `execution_authority_receipt=null/not_applicable`。`ticket_terminal_status=passed` 只能在 result review PASS 后物化；`downstream_activation_status=activated` 又只能在 terminal PASS 后由另一个 `downstream_activation_receipt` 物化。execution authority 与 downstream activation 永不共用同一 receipt。

`action_grant_status=not_granted/consumed/expired/revoked` 时 `granted=false`；只有 `authorized/active` 时 `granted=true`。缺 receipt、前驱、预算、allowlist 或 reviewer 时必须 fail closed。`held` 是一次 ticket 的 terminal 结果；`HOLD_TRIGGER` 是 3.3 的 capability decision，两者不能互换。

`phase0_candidate_awaiting_fresh_review`、`plan_candidate`、`phase6_s4_candidate_authorized`、`phase*_active/pass` 等长标签只能作为由上述原始字段计算出的 boolean `derived_state_flags`，不能作为 enum 输入、receipt verdict 或 action grant。例：`phase0_candidate_awaiting_fresh_review=true` 必须等价于 `phase_status=candidate AND phase_review_status=pending AND downstream_activation_status=pending AND G0_absent=true`；`active` 只能从 `phase_status=in_progress` 与有效 action grant 推导。

为避免 self-reference，candidate manifest 只冻结 `candidate_state` 原始字段与 transition rules；`effective_state` 由 validator 把不可变 candidate manifest、exact review/terminal receipts 和 downstream-activation receipts 联合计算，不能回写 candidate。以 Phase 0 为例，H0 中 `candidate_state.phase_status=candidate`；只有 valid G0 存在时，计算结果才是 `effective_state.phase_status=passed`、`effective_state.downstream_activation_status=activated`，H0 字节保持不变。

validator 必须拒绝非法组合，包括：terminal status 在非 terminal lifecycle 中非 null、ticket 未审即 execution-authorized、result 先于 authority、terminal PASS 缺 result-review PASS、terminal PASS 前 downstream activated、phase PASS 缺 required ticket terminal PASS、program complete 缺全部 completion gate。禁止使用含义不明的 done、ready、green；每个 passed 必须带 scope、证据和 known boundary。

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

以下是 Phase 4 前的候选目标，不授权 Phase 0/1 立即创建整套新目录或批量移动文件。Phase 1 必须先冻结活动 consumer、真实 import cycle、runtime resource exact-digest 绑定和 R3–R14 reachability；Phase 3 spike 可能修正命名，Phase 4 ADR 才能把候选结构变成迁移权威，但职责分层不得反向合并。

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
  compat/
    retrieval_import_shim.py
    research_runtime_adapter.py
    provider_transport_adapter.py

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
    legacy_r14/
  qualification/
  integration/
  product/
  security/

archive/versions/
  # 完整旧实现、origin/redirect/digest 与历史审计；不进入 package discovery
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
| R3–R14 modules | REGRESSION_ONLY | 完整实现只留 Git/history archive；有界 harness/case 放非 package regression root；不进入新生产主路径 |
| apps/workbench | KEEP_PRODUCT + THIN | 留金融 Evidence/Gap/Review/Release；通用 trace/run UI 交成熟平台 |

`src/finsight/compat` 只能容纳当前仍被消费、具 removal ticket 的薄 shim/adapter，不得复制 R3–R14 attempt-specific implementation。历史 replay 只能由显式 `historical_audit`/qualification profile 执行，默认 wheel、Runtime Registry、API/UI 和 CI 主路径不得发现或导入它。

任何真实目录创建、模块移动或 import 重写必须等 Phase 4 ADR 冻结，并在 Phase 5 通过 compatibility shim、import map、consumer tests 和 rollback slice 完成。不得先建立空的“目标架构骨架”，再用它反向证明目标结构合理。

### 5.4 当前真实实现锚点与 Phase 1 必须复现的初查事实

以下是 plan revision 前的只读 surface scan；它们是 Phase 1 的待复现输入，不是未经机器 artifact 固定的最终审计结论：

- 当前产品 composition roots 是 `apps/workbench/backend/app.py`、`scripts/dev/run_workbench_backend.py` 和前端 ResearchWorkspace/Operations，而不是候选 `src/finsight`；
- 当前 `src` 下约有 retrieval 118、sec_agent 65、ingestion 8、financial_facts 5、connectors/evidence 3、indexing 2 个 Python 文件；`sec_agent.research` 约 20 处依赖 retrieval，retrieval 又有 2 处反向依赖 sec_agent，形成真实 package cycle；
- `financial_facts` 约有 4 处依赖 retrieval，属于需要在迁移前拆开的 domain inversion；
- `research_retrieval_service.py` 直接组合约 19 个 retrieval 模块及其他 domain，不是可直接替换的薄 adapter；
- runtime registry 当前按 exact digest 绑定约 28 个资源；移动文件、改内容或只改 import 都可能让 application/replay gate 失败；
- `configs` 约 1,190 份，混合 policy、result、current、attempt 和 audit；`scripts/data_retrieval` 与 `scripts/research` 混合正式 runner、一次性工具、live/zero-call 路径；
- `data` 总量约 74.69 GiB，其中 `data/indexes` 约 25.93 GiB；容量不是删除授权，producer/input/consumer/rebuild map 仍是前置条件；
- `pyproject.toml` 已声明 contract、integration、full-chain、paid/network/local-data 等 marker vocabulary，但约 200 个 test 尚未完成逐测试分类；默认 pytest 是否会意外触发本地数据、网络或付费调用仍需证明；
- 当前仓库没有已冻结的 ports/adapters/infrastructure/legacy package 边界，不能把候选目录图误报为现状。

Phase 1 必须以可重放命令和机器输出复现或修正这些数字；若结果不同，保留差异并解释时间点、扫描规则和 consumer 定义，不得静默覆盖。

## 6. 程序拓扑、提交拓扑与变更控制

### 6.1 程序依赖

~~~text
Plan-only commit C0
        |
        v fresh read-only plan review
Phase 0 candidate H0
  machine manifest + source docs + tests
  Phase 1 authority still false
        |
        v fresh read-only exact-H0 review
Phase 0 PASS receipt G0
  G0.parent=H0; only materializes review receipt
  effective Phase 1 bounded read/audit-write authority becomes true
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

Phase 1 与 Phase 2 可在 G0 后分别按 ticket 并行，但 Phase 2 shortlist 必须消费 Phase 1 已确认的 capability constraints，Phase 3 只能消费二者冻结的输入。Phase 5 不能在 Phase 4 ADR 前开始。Phase 6 不能用尚未通过 Phase 5 slice gate 的组件。Phase 7 不能删除或退休仍被活动 consumer 使用的旧代码。

### 6.2 提交拓扑

1. C0：只包含本执行程序。
2. C0-review：fresh、作者分离、只读 reviewer 返回结构化 verdict；reviewer 不写仓库。
3. H0：物化 C0 plan review receipt，并提交 Phase 0 candidate machine manifest、必要 source-doc supersession、Project OS、checklist、worklog 和定向测试。H0 内 manifest 的原始字段必须写 `candidate_state.phase_status=candidate`、`candidate_state.phase_review_status=pending`、`candidate_state.downstream_activation_status=pending`、`G0_absent=true`，并由此计算 `derived_state_flags.phase0_candidate_awaiting_fresh_review=true`；所有 Phase 1+ 权限仍为 false。H0 changed paths 必须排除 plan path，且 `H0:<plan path>` 的 Git blob、raw SHA-256 和 bytes 必须与 C0 完全相等。
4. H0-review：另一名 fresh、作者分离、只读 reviewer 只审 exact H0；reviewer 不写仓库。若发现 P0/P1/P2，H0 保持不可变，先物化 failure receipt，再创建非覆盖 H1 candidate。
5. G0：仅当 H0 review 为 `PASS 0/0/0/*` 时，创建固定路径的 Phase 0 PASS receipt。G0 必须满足 `G0.parent=H0`、changed path 仅该 receipt、H0 machine manifest 与 plan blob/SHA/bytes 不变。有效 Phase 1 权限由 H0 manifest＋G0 receipt 联合计算；不允许自引用 G0 commit。
6. 后续每个 action-bearing release slice 独立提交：candidate contract → candidate review → execution-authority receipt → implementation/run → frozen result → result review → terminal receipt → 可选 downstream-activation receipt。execution authority 必须先于动作，downstream activation 必须后于 terminal PASS；失败 slice 不覆盖。
7. 大型组件安装和 run artifact 不进 Git；Git 只保存 lock、manifest、digest、license/SBOM 结论、测试代码和有界结果。
8. 不为每个小状态创建独立 current manifest。维护一个 canonical program manifest，加 append-only candidate/candidate-review/execution-authority/result/result-review/terminal/downstream-activation receipts；任何 PASS 都不能在被审 candidate 中自我声明。

### 6.3 计划修订

本计划可修正，但需同时满足：

- 新证据写入 issue/capability ledger；
- 说明原假设、证据、影响、选择与 rollback；
- 计划合同版本仅在行为/门/接口变化时递增；
- 任何计划行为、门、权限或接口变化都必须形成新的 plan-only `C1/Cn`，重新接受 exact plan review；不得夹带在 H0、G0 或普通 phase/ticket commit；
- 纯运行重试只增加 rN，不增加合同版本；
- 涉及产品范围、发布含义、付费规模、安全或不可逆动作时再次向 Owner 报告；
- 已完成/失败的历史证据不回写。

### 6.4 权限状态机：允许“做什么”与允许“把什么当真”分开

程序采用 deny-by-default。章节标题、计划顺序、代码已存在或候选安装成功都不构成权限。机器合同必须同时维护：

1. `phase_state`：3.2 的 `phase_status`、`phase_review_status` 与证据绑定；
2. `ticket_state`：predecessor、`ticket_lifecycle_stage`、`ticket_terminal_status` 及 candidate/candidate-review/execution-authority/result/result-review/terminal receipts；
3. `downstream_activation_state`：terminal PASS 后的独立 activation status/receipt；
4. `action_grants`：3.2 的 `granted:boolean`＋`action_grant_status`，说明允许执行的动作；
5. `domain_authority`：Candidate、Evidence、NumericFact、S2、S3、report、human、product/release 的权威；
6. `allowed_roots_and_surfaces`：动作能读写的精确路径、服务、API、数据类型与消费者。

每个 `action_grant` 至少包含：

- stable action ID 和 `default=false`；
- grant phase/ticket；
- exact authority commit/receipt；
- predecessor gate；
- allowed roots/surfaces 和显式 deny roots；
- input manifest/digest；
- budget/TokenBudgetBasis（适用时）；
- start/expiry/consumption；
- stop、rollback 和 reviewer receipt。

最低动作矩阵如下；未来 machine registry 可以增加更细动作，不能合并这些行：

| Action ID | 最早可能 grant | 允许范围 | 不随之获得的权威 |
|---|---|---|---|
| h0_governance_materialization_write | H0 one-shot | C0 plan review receipt、source supersession、Project OS、worklog、governance config/test exact allowlist；plan path 显式 deny | plan mutation、component adoption、产品行为 |
| phase1_audit_read_and_bounded_write | G0 | repo/data metadata 只读；Phase 1 docs/configs/audit artifacts 写入 | src/product data mutation、component execution |
| phase2_network_research | G0＋RSH execution-authority receipt | 官方 docs/repo/spec/paper 调研与来源快照 | external source product call、package download |
| phase3_qualification_contract_evidence_write | Phase 3 exact QL candidate-contract authority receipt | candidate manifest 先行；仅 scripts/tests/configs/docs 的 qualification/audit/worklog exact paths，以及 lock/revision/SBOM/bounded candidate/review/authority/result/terminal receipts | production src、pyproject/current config/data、component promotion、domain authority |
| production_integration_code_test_config_lock_write | Phase 5 MIG execution-authority receipt；Phase 0/3 各有独立受限动作 | exact MIG slice allowlist | Evidence/S2/S3/report/release |
| package_model_image_download | Phase 3 QL execution-authority receipt | Z qualification lab exact roots | dependency promotion、模型调用 |
| qualification_service_install_start | Phase 3 QL execution-authority receipt | 隔离端口、进程、容器、Z roots | current product route |
| qualification_service_stop_uninstall | 与 install/start 同一 QL candidate contract 预授权，失败/stop/expiry 时才可消费 | exact candidate process/service/container/env/image；只允许停止及移除无共享引用的 candidate 资源 | current/promoted/shared service、current product data、其他 candidate |
| local_fixture_benchmark | Phase 3 QL execution-authority receipt | frozen/synthetic fixtures | human/product truth |
| external_source_call | 单独 Phase 3/6 source execution-authority receipt | exact domain/request/data class | Evidence admission |
| provider_model_call | 单独 Phase 3/6 model execution-authority receipt＋TokenBudgetBasis | exact model/deployment/profile/request budget | Evidence/NumericFact/S2/S3/release |
| qualification_index_or_data_write | Phase 3 QL execution-authority receipt | Z lab；若含 D 必须 exact explicit root | current index/data authority |
| shadow_artifact_write | Phase 3 QL / Phase 5 MIG execution-authority receipt | unadmitted candidate namespace | Evidence/NumericFact/judgment |
| qualification_candidate_artifact_retire_delete | terminal failed/held QL result 或 exact rollback authority receipt | exact candidate-local qualification index/data/artifact roots | D current indexes、current/promoted/admitted data、冻结 failure/corpus/receipt |
| unadmitted_shadow_artifact_retire_delete | Phase 3/5 exact candidate/slice rollback authority receipt | exact unadmitted shadow DB/object/projection namespace | current/promoted/admitted artifact、historical evidence、其他 slice |
| migration_slice_stop_disable | 与 Phase 5 MIG candidate contract 同时预授权，失败/stop/expiry 时才可消费 | exact non-current candidate route/writer/exporter/feature switch | current consumer expansion、cutover、其他 slice |
| unconsumed_migration_scaffold_retire_delete | Phase 5 exact MIG rollback authority receipt | 仅本 slice 新建且 imports/registry/current consumers=0 的 exact scaffold paths | current/legacy/historical source、其他 slice、product data |
| dual_read_compare | Phase 5 MIG execution-authority receipt | frozen old/new readers，不改变 current consumer | cutover、retire |
| current_consumer_cutover | Phase 6 对应 `ACC-Sn downstream_activation_receipt`；该票已 terminal PASS | exact consumer/feature flag，以及同一 grant 预授权的 last-active-qualified-route rollback | 后续 S-stage、publication/release、新 route expansion |
| old_index_delete | 独立 index-retirement authority receipt | 仅通过 10.6 硬门的 direct target roots | new retrieval active |
| legacy_source_retire_delete | Phase 7 CLS-03 execution-authority receipt | active imports/registry/consumers=0 的 exact paths | historical evidence deletion |
| evidence_admission | Phase 6 `ACC-S1 execution_authority_receipt` | qualified Candidate→Evidence | NumericFact/S2/S3 |
| numeric_fact_and_s2_authority | Phase 6 `ACC-S2 execution_authority_receipt` | qualified FactObservation→NumericFact/bridge | S3/report/release |
| s3_research_judgment | Phase 6 `ACC-S3 execution_authority_receipt` | evidence-bound research judgment | human approval/release |
| report_candidate_generation | Phase 6 `ACC-S4-CANDIDATE execution_authority_receipt` | non-released report candidate | current reader deliverable、qualified-human approval、publication/release |
| qualified_human_approval | Phase 6 `ACC-S4 execution_authority_receipt`；其 predecessor 为 `ACC-S4-CANDIDATE terminal PASS` | exact S4 case/report/review packet 与 denominator | product acceptance、publication/release |
| qualified_human_product_acceptance | Phase 6 `ACC-S5 execution_authority_receipt`；其 predecessor 绑定 `ACC-S4 terminal PASS` digest＋downstream activation | exact end-user workflow/product acceptance packet | publication/release |
| product_publication_release | Phase 6 `ACC-S5 terminal PASS` digest＋downstream activation＋Phase 7 Owner release receipt | exact product/version/deployment | 任何未列 scope |

Phase 3 的 qualification repo write 必须在任何 download/install/run 前先物化 candidate contract；candidate、result、review、activation 分离，失败 append-only，不能运行后补写 candidate 来反向授权既有动作。其 allowlist 只能包含 `scripts/qualification`、`tests/qualification`、`configs/qualification`、`configs/audits`、qualification research/worklog 等 candidate-specific 路径；不得修改 production `src`、`pyproject.toml`、正式依赖锁、current product config/data 或 domain authority。

停止/卸载和清理不是 install/write 的隐含反向动作。`qualification_service_stop_uninstall` 必须在 install/start 前由同一 QL candidate contract 预授权，`migration_slice_stop_disable` 必须在 MIG implementation/run 前由同一 slice contract 预授权，使失败时可以立即 fail closed；消费时仍须绑定 exact process/service/container/env/image 或 route/writer/exporter/feature-switch identity、active/shared-reference proof 和 post-action receipt。candidate/shadow/scaffold delete 动作只有在 terminal result/failure/rollback receipt、exact target manifest、必要 failure evidence/digest 已保留、active handle/service/import/registry/current-consumer proof 完成后才可消费；执行后必须追加 actual target、released bytes 与 recoverability receipt。目标出现 shared/promoted/admitted/current 引用、D current indexes、历史 frozen failure/corpus/receipt、legacy/current source、其他 slice 或 containment/identity 不确定时保持 false 并停止。

Phase 5 最多取得 production integration code/test/config/lock 写入、qualification-only data、shadow 和 dual-read 权限；它不能签发 Evidence、NumericFact、S2/S3 judgment、reader deliverable、human approval 或 release。Phase 6 的每个 `current_consumer_cutover` grant 必须在对应 ticket terminal PASS 后，由独立 downstream activation receipt 同时冻结 last-active qualified route 和 exact rollback authority；rollback 只能回到该已验证旧 route，不能借回滚扩展新 consumer。

Phase 6 也不是一次性打开全部下游。`ACC-S1`、`ACC-S2`、`ACC-S3` 分别先通过 candidate review 获得 execution authority，产生并审查结果，物化 terminal PASS，最后以独立 downstream activation 允许下一阶段；后序 PASS 不能补偿前序 FAIL。S4/S5 固定为：

~~~text
ACC-S3 terminal PASS + downstream activation
  -> ACC-S4-CANDIDATE candidate review + execution authority
  -> non-released report result
  -> author-separated report review/repair PASS
  -> ACC-S4-CANDIDATE terminal PASS
  -> ACC-S4 candidate review + execution authority
  -> exact qualified-human decisions
  -> immutable human result + denominator/binding/authority review
  -> ACC-S4 terminal PASS
  -> independent ACC-S4 downstream activation
  -> ACC-S5 candidate review + execution authority
  -> operations/security/rollback/end-user + qualified-human product-acceptance results
  -> ACC-S5 terminal PASS
  -> independent ACC-S5 downstream activation
  -> Phase 7 Owner release receipt
~~~

`ACC-S4-CANDIDATE` execution authority 只能授予 `report_candidate_generation`；`ACC-S4` execution authority 只能授予 exact S4 `qualified_human_approval`；`ACC-S5` execution authority 可以授予 exact `qualified_human_product_acceptance`，三者都不能授予 publication/release。所有 execution-authority 阶段产生的 Evidence/NumericFact/judgment/report/human/product artifacts 在本票 terminal PASS＋downstream activation 前只能存在于 exact ticket-scoped、不可被 current consumer 读取的 namespace。

`ACC-S4 execution_authority_receipt` 必须在 human action 前绑定 exact case/report/review packet、required-item denominator、author/reviewer/human 身份和角色分离、admit/reject/rebind/defer/reopen vocabulary、allowed action、expiry/consumption、no-current/no-release deny，以及 result/review/terminal/downstream receipt fixed paths。`ACC-S4 terminal_receipt` 必须逐字节绑定 report-review digest、immutable human-result digest、完整 denominator 与 authority review；所有 required items 必须有 terminal disposition，deny/defer/timeout 不得当 PASS。`ACC-S5.predecessor` 又必须逐字节绑定该 terminal receipt result digest 和 downstream activation receipt identity。Phase 7 只允许在 consumer/rollback/root-cause/release 条件分别满足后收口，不因“项目结束”获得广义删除权。

machine manifest 必须在 `candidate_state` 中存 3.2 的原始轴与 transition rules；允许额外输出只读 derived booleans，如 `phase0_candidate_awaiting_fresh_review`、`phase6_s4_report_candidate_authorized`、`phase6_s4_human_authorized`、`phase6_s4_terminal_pass`、`phase6_s5_terminal_pass`。`effective_state` 与这些 derived flags 必须由 validator 从不可变 manifest＋receipts 重算，不得作为 transition、PASS 或 grant 的输入。并行只通过各 phase/ticket 独立原始状态表达；不得用一个粗粒度 `current_phase` 或长状态字符串覆盖事实。

### 6.5 可机检 ticket/slice registry

Phase 0 必须创建 machine-readable `program_ticket_registry_v1`。每条记录至少包含 stable ID、capability family、owner/author/reviewer/human roles、exact input path/schema/digest、output path/schema、predecessor receipt/digest、requested/granted authority、资源预算、TokenBudgetBasis 引用、acceptance、stop、rollback、`ticket_lifecycle_stage`、`ticket_terminal_status`、`downstream_activation_status`，以及独立的 candidate、candidate-review、execution-authority、result、result-review、terminal、downstream-activation receipt paths/identities。没有执行动作时 execution-authority receipt 显式为 null/not_applicable；没有下游消费时 downstream activation 显式为 not_applicable。

稳定 ID 命名空间：

- Phase 0：`P0-01` 至 `P0-09`；
- Phase 1：`P1-01` 至 `P1-15`；
- Phase 2 families：`RSH-01` 至 `RSH-15`，对应 9.3 的十五个技术面；
- Phase 3 qualification：`QL-01` 至 `QL-13`，每个 candidate 使用 `QL-xx-Cnn`；
- Phase 4：`ADR-01` 至 `ADR-14`，并生成 `migration_slice_registry_v1`；
- Phase 5：`MIG-{capability}-{nn}`，每个 slice 单变量、单 feature switch、单 rollback；
- Phase 6：`ACC-S1`、`ACC-S2`、`ACC-S3`、`ACC-S4-CANDIDATE`、`ACC-S4`、`ACC-S5`，另有 `R14-REPLACEMENT-S1-CLOSURE`；
- Phase 7：`CLS-01` feasibility、`CLS-02` dependency cleanup、`CLS-03` legacy retirement、`CLS-04` operations/rollback、`CLS-05` Project OS、`CLS-06` final independent review/Owner recommendation。

Phase transition 只能由 registry 的 required tickets terminal PASS、exact terminal digest 和独立 downstream-activation receipt 计算；execution-authority receipt 只能授权本票动作，不能冒充 terminal PASS 或下游激活。自由文本“已完成”没有机器效力。Phase 5 不得开始，直到 Phase 4 registry 被 fresh review，且所有将执行 slice 已有精确授权、回滚和 stop contract。

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
| P0-03 program candidate | C0 identity、phase/action/ticket/domain-authority matrix、deny set | configs/repository/fin_0_1_3_product_wide_architecture_rebase_execution_program_v1_0.json | H0 candidate_state.phase_status=candidate、phase_review_status=pending、G0 absent；Phase 1+ false |
| P0-04 source supersession | 产品审计、成熟栈包、R14 plan/I2、baseline docs | 原位 owner-decision/supersession notes | 不改写历史结论 |
| P0-05 Project OS | capability/root-cause/current context/checklist/README | append-only current state | JSONL parse、current context一致 |
| P0-06 governance test | machine authority、C0 Git binding、H0/G0 非自引用激活、plan immutability、3.2 状态轴 | tests/test_product_wide_architecture_rebase_program.py | H0 diff 排除 plan 且 H0 plan blob/SHA/bytes=C0；非法状态组合 fail closed；无 G0 receipt 时 Phase1=false；exact PASS receipt 后仅 Phase1 audit=true |
| P0-07 worklog | 所有变更、命令、未执行项 | docs/worklog/fin_0_1_3_architecture_rebase/001_phase0_program_freeze_and_authority.md | factual、可恢复 |
| P0-08 exact H0 review | clean H0 candidate | fresh read-only review payload | P0/P1/P2=0/0/0；writes=0；plan unchanged/excluded |
| P0-09 G0 downstream activation | H0 PASS payload | fixed Phase 0 PASS/downstream-activation receipt only | G0.parent=H0、one changed path、H0 manifest 与 plan blob/SHA/bytes 不变、effective Phase0=passed、仅 Phase1 audit=true |

### 7.4 Phase 0 机器合同最低字段

- schema_version、program_id、contract_version、3.2 全部原始状态轴与可重算 derived flags；
- owner_decision_at、owner_decision_summary；
- canonical_branch、C0 plan path/commit/tree/parent/blob/raw SHA-256/bytes、H0 expected parent=C0；
- fixed C0 plan review receipt path、fixed G0 Phase 0 downstream-activation receipt path、H0/G0 changed-path rules；
- H0 action allowlist/denylist；plan path 必须在 denylist，且 H0/G0 plan blob/raw SHA-256/bytes 必须等于 C0；
- product_version、S-stage status、R14 implementation freeze；
- R14 disposition、failure counts、open root causes；
- per-phase status/review vector、ticket lifecycle/terminal/downstream-activation vector、phase sequence、transition rules；
- machine ticket registry 与 migration slice registry schema；
- action grants、domain-authority matrix、allowed/denied roots and surfaces；
- component promotion、model、network、paid、external、shadow、dual-read、cutover、Evidence、NumericFact、S2/S3/report/human/product/release booleans；
- data/index destructive boundary；
- source docs、ledgers、review receipt；
- change control、stop conditions、known boundary。

### 7.5 Phase 0 退出门

- plan fresh review 无 P0/P1/P2；
- H0 machine config 与 exact plan commit 一致，并在 review 前不自报 PASS；H0 changed paths 排除 plan，且 H0 plan blob/raw SHA-256/bytes 与 C0 相等；
- fresh H0 review 无 P0/P1/P2；G0 只物化 fixed PASS receipt，且 H0 manifest 与 plan 均保持原 blob/raw SHA-256/bytes；
- 3.2 每个原始状态轴均使用合法 enum/boolean，所有非法 lifecycle/terminal/grant/activation 组合在 mutation test 中 fail closed；H0 candidate_state 不被回写，valid G0 只改变 validator 计算出的 effective state；
- R14 在所有 current source 中均为 strategic termination / not PASS；
- RC-S1-109/110 仍 open；
- RC-S0-111 记录为 owner-authorized architecture rebase、effective Phase 0 passed，但 issue 仍 open 且 migration authority=false；
- no R15/R16；
- effective authority 只新增 Phase 1 bounded read/audit write；no component/model/network/package/service/code migration/shadow/cutover/delete/domain authority 被意外打开；
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

### 8.3 执行顺序

Phase 1 不是并行填写十五张表。先执行 P1-01、P1-02、P1-04、P1-10，冻结活动入口、package cycle、runtime resource compatibility spine 与 R3–R14 reachability；这四项未通过前，禁止创建目标目录、移动模块或把某个旧模块宣布为 retired。随后执行 P1-03、P1-05 至 P1-13，最后由 P1-14 汇总迁移矩阵、P1-15 冻结 ports 和验收合同。

### 8.4 需求票

| Ticket | 工作内容 | 主要输出 |
|---|---|---|
| P1-01 baseline and active consumers | Git/baseline、backend/frontend composition roots、CLI/API/worker、runtime entrypoints | active_consumer_graph_v1 |
| P1-02 package graph and cycle plan | Python/TypeScript imports、dynamic imports、service composition、domain inversion | package_dependency_and_cycle_break_plan_v1 |
| P1-03 domain-kernel extraction | identity/source/Evidence/Numeric/PIT/bridge/Gap/WWC/release | fin_domain_kernel_map_v1 |
| P1-04 runtime-resource compatibility spine | runtime registry、exact digest、resource path、replay/app consumers | runtime_resource_compatibility_map_v1 |
| P1-05 artifact/data/index map | raw/source/object/index/SQL/model/trace/eval/report/private/public | artifact_lineage_and_rebuild_map_v1 |
| P1-06 S1 capability map | capture/document/XBRL/index/retrieval/ranking/semantics/Evidence | s1_capability_and_authority_map_v1 |
| P1-07 S2 capability map | financial fact/normalization/bridge/derivation/forecast inputs | s2_capability_and_authority_map_v1 |
| P1-08 S3 capability map | causal/counter/WWC/gap/research method/model nodes | s3_capability_and_authority_map_v1 |
| P1-09 S4/S5 and product map | writer/citation/render/review/release/workbench/operations | s4_s5_product_capability_map_v1 |
| P1-10 legacy R-chain reachability | R3–R14 files、tests、fixtures、current consumers、historical-only paths | r_chain_legacy_disposition_v1 |
| P1-11 config and runner taxonomy | 1,000+ configs、formal/one-off/current/result/policy、live/zero-call runners | config_and_runner_taxonomy_v1 |
| P1-12 test/eval spine | declared markers、逐测试分类、gold/blind/replay/integration/full-chain、default pytest safety | test_and_eval_spine_v1 |
| P1-13 dependency/deploy/SBOM | direct/transitive deps、duplicate capability、platform/privacy/license constraints | dependency_deployment_and_license_baseline_v1 |
| P1-14 unified migration matrix | retain/wrap/replace/regression/retire、owner、consumer、risk、wave、rollback | capability_migration_matrix_v1 |
| P1-15 ports and acceptance contracts | canonical schema、IDs、failure codes、receipts、API/UI、fixtures、shadow parity | target_ports_and_qualification_input_v1 |

### 8.5 每个模块必须回答

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

### 8.6 Phase 1 输出路径

- docs/architecture/repository/FIN_0_1_3_PRODUCT_CAPABILITY_AND_LEGACY_MIGRATION_INVENTORY_20260830.zh-CN.md；
- configs/repository/fin_0_1_3_product_capability_migration_matrix_v1_0.json；
- configs/repository/fin_0_1_3_active_consumer_and_artifact_rebuild_map_v1_0.json；
- configs/repository/fin_0_1_3_runtime_resource_and_r_chain_compatibility_map_v1_0.json；
- configs/repository/fin_0_1_3_test_eval_and_runner_taxonomy_v1_0.json；
- 对现有 code map 的增量 supersession note；
- Phase 1 worklog 和 fresh read-only review receipt。

### 8.7 退出门与停止条件

通过要求：

- S1–S5 每个产品能力都有 owner 和 decision；
- 所有活动 import/consumer 都有归属；
- package cycle、domain inversion 与 runtime exact-digest 绑定均有可回滚拆解顺序；
- 所有大 artifact 都有 producer、input、rebuild、consumer、retention；
- R3–R14 不再被误标为多个活动产品版本；
- 所有 test 都按已声明 marker vocabulary 分类，默认测试路径不会意外触发 local-data、network 或 paid-model；
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

进入任何 candidate 的下载、安装、启动或运行前，必须先创建并提交该 candidate 的 `QL-xx-Cnn` qualification contract/manifest，接受 candidate review，并由独立 execution-authority receipt 授权 exact 动作。该 candidate commit 只能使用 `phase3_qualification_contract_evidence_write`，exact allowlist 必须逐路径列出 `scripts/qualification/`、`tests/qualification/`、`configs/qualification/`、`configs/audits/`、qualification research/worklog 中本 candidate 的文件；production `src/`、`pyproject.toml`、正式依赖锁、current product config/data 均为显式 deny。candidate、candidate review、execution authority、run result/failure、result review、terminal receipt、downstream activation 必须是互不覆盖的独立对象；run 不能反向给 candidate 补授权，review 不能改实现，任何 activation 都不能改 manifest 或 result。

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
- `ticket_terminal_status`：passed/failed/stopped/held/superseded；
- 另行记录 3.3 `capability_disposition` 与 component role；不得把 pass/fail/hold/winner/challenger/ceiling 混在一个 decision 字段。

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
| QL-07 embedding | BGE-M3 vs Qwen3-Embedding bounded local candidates + managed ceiling if approved | fixed qrels、identifier zero-miss、target-in-pool、Recall@k、critical issuer/period/unit/source-role slices、p95、RAM/VRAM、index bytes、rebuild |
| QL-08 retrieval engine | fixed qualified embedder；PostgreSQL+pgvector vs OpenSearch | 单一 embedding input 下的 PIT/Recall/MRR/nDCG/p95/rebuild/operations |
| QL-09 rerank | qualified candidate pool；BGE v2-m3 vs managed ceiling | target-in-pool first、material slice、latency/resource |
| QL-10 semantic | LangExtract pattern + DeepSeek shadow | exact span/schema/hard validator/abstain/human gold |
| QL-11 workflow/provider | LangGraph + official SDK | max_retries=0、checkpoint、HITL、duplicate-risk、crash recovery |
| QL-12 trace/eval | OTel/OpenInference + MLflow | passive import、privacy、export、authority independence |
| QL-13 rendering | Quarto/Pandoc/CSL | claim/citation precheck、PDF/DOCX/HTML visual parity |

QL-07 必须独立冻结 model/revision/weights/tokenizer、pooling、normalization、dimension、precision/quantization、max length/truncation、dense/sparse/multi-vector mode、batch/device。只有 QL-07 得到 winner 或有证据的 KEEP/HOLD，QL-08 才能在固定 embedder 上比较 index engine；只有 QL-08 的 target-in-pool/candidate pool 通过，QL-09 才能比较 reranker。若沿用 current embedding，也必须有独立 KEEP/HOLD receipt，不能隐含在 retrieval 结果里。

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
8. 已向 Owner 在执行更新中报告将触发该授权；
9. `known_non_reproducible_items == []`，每个 producer/config/commit 与全部 retained input digest 都可读且验证成功；
10. 每个删除目标已满足下列恢复路线之一，并有 fresh review：
    - content-addressed old-index snapshot/export 已写入独立受控根，并完成一次 restore drill；或
    - 已从冻结输入在独立 scratch root 成功 rebuild，且通过旧 query/index contract、identifier zero-miss、row/object count、known regression 和 digest/semantic equivalence；
11. exact target manifest、恢复证明、active-handle/service proof、Owner 通知和 authority grant 已进入一个先提交的 index-retirement authority receipt；该 receipt 没有 PASS 时 delete action=false。

若无法满足第 9–11 项，即使磁盘不足也必须停止或缩小 candidate，不得把“已记录不可复现风险”当成删除许可。

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
- snapshot/export/restore 或 isolated rebuild proof；
- target canonical path、volume serial/file identity、link count/reparse status/ADS 检查；
- root ACL/owner/audit policy、active handle/service proof；
- before-free-space 和预计释放。

删除边界：

- D:\FIN_Insight_Agent\data\indexes 根本身永远不是删除目标，根必须原位保留，ACL、owner、ADS、audit/mount 语义不变；
- 只枚举执行时该根的 direct children 作为显式 target roots，再在每个已验证 target root 内递归；不得对根执行 recursive delete；
- D:\FIN_Insight_Agent\data\staging 不在范围；
- data\processed_private、raw/source/object、workbench_private、eval/report、R14 evidence、Codex live state 均不在范围；
- 即使存在同名 staging，只有位于 data\indexes 内的后代才属于本授权；
- 必须在一个 PowerShell 流程中解析、验证全部 absolute target，再逐项 Remove-Item -LiteralPath；每个 target 的 resolved/canonical path、volume/file identity 必须仍在同一根内；
- 根或任一 target/descendant 出现 reparse point、junction、symlink、mount point、无法解释的 hard-link/reflink、alternate data stream 或 containment/file-identity 漂移时立即停止；
- 禁止 glob、环境变量拼接、跨 shell 删除和 broad recursive target。

删除后：

- 记录实际删除项、释放空间和是否可恢复；
- 在独立 post-delete receipt 中绑定 pre-delete authority、实际 target、实际释放字节和恢复路线状态；
- old retrieval status=temporarily_suspended_for_architecture_rebuild；
- 所有依赖旧 index 的命令/API/UI 必须 fail visibly，不能静默返回空结果或 public gap；
- 新 retrieval 只有通过 input digest、row/object count、identifier zero-miss、query suite、known regression、lineage、rebuild、backup/restore 和 fresh review 后才可恢复 active。

### 10.7 Phase 3 退出门

- 每类能力有 default/challenger/managed ceiling role，或有证据的 `HOLD_TRIGGER/EXCLUDE` capability disposition；
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
| W0 | namespace/ports/contracts scaffold，不改产品结果 | Phase 4 ADR | 以 `unconsumed_migration_scaffold_retire_delete` 删除新未消费 scaffold |
| W1 | passive trace/experiment/contract validation | QL-01/12 | 以 `migration_slice_stop_disable` 关闭 exporter，FIN artifact 不变 |
| W2 | source/XBRL/document intake adapters shadow/dual-read | QL-02/03/04/05 | 以 `migration_slice_stop_disable` 关闭 candidate adapter；旧 capture 始终是 current，保留 shadow artifact |
| W3a | canonical metadata passive projection | QL-01/06 | 以 `migration_slice_stop_disable` 停止 projection；canonical FIN artifact 不变 |
| W3b | artifact/storage shadow | QL-06 | 以 `migration_slice_stop_disable` 关闭 shadow writer；以 `unadmitted_shadow_artifact_retire_delete` 删除未晋升 shadow DB/objects |
| W3c | fixed qualified embedder 下的 index-engine A/B | QL-07/08 | 以 `qualification_candidate_artifact_retire_delete` 丢弃 qualification indexes；旧 index 不变 |
| W3d | retriever dual-read | W3c winner + exact query contract | 以 `migration_slice_stop_disable` 关闭 candidate reader；旧 retriever 始终是 current，不改 admission |
| W3e | target-in-pool 后的 reranker shadow | QL-09 + W3d candidate pool pass | 以 `migration_slice_stop_disable` 关闭 reranker；保留原 candidate order |
| W4a | provider SDK saved/synthetic fixture parity | QL-11 provider sub-result | 以 `migration_slice_stop_disable` 关闭 candidate transport；旧 transport 始终是 current，无 live call |
| W4b | workflow/checkpoint over saved provider fixtures | QL-11 workflow sub-result + W4a | 以 `migration_slice_stop_disable` 关闭新 workflow；current runner/checkpoint namespace 从未切换 |
| W4c | semantic candidate shadow | QL-10 + qualified human gold | 以 `migration_slice_stop_disable` 关闭 semantic route；以 `unadmitted_shadow_artifact_retire_delete` 删除未准入 shadow projection |
| W4d | provider/workflow/semantic bounded integration | W4a/W4b/W4c 分别 PASS | 以 `migration_slice_stop_disable` 关闭整体 feature flag；三个独立 rollback 均可执行 |
| W5 | non-released report/render/review UX candidate preview | QL-13 + Workbench contract | 以 `migration_slice_stop_disable` 关闭 candidate preview；旧 renderer/read surface 始终是 current |
| W6 | Phase 6 controlled consumer cutover 与 legacy regression-only | 对应 ACC-Sn terminal PASS＋downstream activation | compatibility shim re-enable；不恢复 attempt-specific R3–R14 |

Wave 只是排序容器，不是一次实现提交。W3a–W3e、W4a–W4d 每项必须是独立 `MIG-*` slice，分别具有 input digest、feature switch、result、fresh review 和 rollback；不得用一个 W3/W4 commit 同时改变多项变量。

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

S4/S5 的机器顺序采用 6.4 的完整序列。`ACC-S4-CANDIDATE` 票据仅存在、仅 candidate commit 或自由文本状态都不产生权限；只有合法 execution-authority receipt 才能临时打开 `report_candidate_generation`。report result/review 后必须先得到该子票 terminal PASS，主票 `ACC-S4` 的 execution-authority receipt 才能打开 exact human action；human result/denominator/authority review 后才能 terminal PASS，并另行 downstream activate。`ACC-S5.predecessor` 必须绑定该 terminal digest 与 downstream receipt；qualified-human product acceptance 完成并审阅前不得 ACC-S5 terminal PASS。全过程 current reader publication/release 继续为 false。

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
- required-item denominator 完整，deny/defer/timeout 不当 PASS；
- author/reviewer/human 身份与角色分离；
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
- immutable qualified-human product-acceptance result 与 denominator/review digest；
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

### 13.5 `R14-REPLACEMENT-S1-CLOSURE` 同阶段关闭票

这张票独立于 QL-10 semantic 安装/小切片资格，也独立于通用 `ACC-S1`。QL-10 PASS 只说明候选可继续；不能关闭 RC-S1-109/110、不能退役旧回归证据。

固定输入至少包括：

- R14 implementation freeze=`7e25cad95ee84b39fb2a51063100405bc27da6e5`；
- frozen source：1,888 rows，SHA-256=`d4c7e51790713d32fc10a9d0382b617f8ebd60861a3741d3adcee34392045d45`；
- frozen compiled：34,199 rows，SHA-256=`1c3e48486f933d23306dbabacb1641e26cb9bbc5b474da932d602752dff3fa92`；
- full corpus=`27,026`，原 preview=`26,787 pass / 239 fail`；
- case failure inventory digest=`49acf114c03ab97e059ee3bd928736d06d70b1d5a6d8d3af2dcdfabc68e2a5d1`；
- event mismatch inventory digest=`68d267f77400a350cd698bf3c4baf7152067b437290084596a4fa370965276e5`；
- mismatch events=`277`，四形态=`246/9/5/17`；
- 原 population/event/price/property/mutation/resource/transaction/privacy validators 与 gates。

必须分层保存 old parser output、new deterministic/LLM SemanticCandidate、hard-validator output、abstain/human route 和 case-correct human-adjudicated gold。旧 parser 与旧 validator 的错误输出只是 regression/adversarial baseline，不是真值；模型输出也不是真值。

关闭验收同时要求：

1. 239/239 failed cases 与 277/277 mismatch events 均有 case-correct human adjudication；
2. replacement 对 full frozen corpus 的 validation 为 27,026/27,026，277/277 mismatch 已依新真值消除；允许模型 abstain，但必须在该冻结资格内由预声明 human route 形成最终 adjudicated outcome，不能把 abstain 当自动 PASS；
3. zero new failure code，原 population/event/price/property/mutation/resource/transaction/privacy gates 不弱化；
4. 禁止 case key、text SHA、event ID、first-exception 或已知例句特判；
5. exact-span、strict schema、hard validator、abstain/escalation、materiality slice 与未观察异质 case 均通过；
6. old/new full-corpus regression、mutation 与 fresh author-separated read-only review 为 PASS；
7. review PASS 后仍由 Owner 以独立 receipt 明确关闭、合并或重新处置 RC-S1-109/110；R14 自身永久保持 not PASS。

任何一项不满足，RC-S1-109/110 继续 open，replacement 不能成为 current consumer，Phase 7 只能标 `partial/stopped`，不得标 `complete`，也不得删除冻结 R14 failure/corpus/validator/harness。

### 13.6 Phase 6 退出门

- 关键金融 slice 无未解释 P0/P1；
- deterministic、model、human 三层结果分开；
- DeepSeek 真实 case 不是 self-judge 唯一标准；
- `ACC-S4-CANDIDATE` report result/review terminal PASS、`ACC-S4` qualified-human immutable result/denominator/authority review terminal PASS、独立 downstream activation 均完成；
- `ACC-S5.predecessor` 精确绑定 ACC-S4 terminal digest/downstream receipt，qualified-human product acceptance 与 product review terminal PASS；
- cost/latency/resource/security/operations 可接受；
- old/new comparison 与 rollback 演练通过；
- S1–S5 各自 verdict 明确；
- `R14-REPLACEMENT-S1-CLOSURE` 已 PASS 且 Owner 已处置 RC-S1-109/110，或程序明确以 partial/stopped 收口而非 complete；
- 不通过弱化 validator、删 case 或隐藏失败得到 PASS。

## 14. Phase 7：迁移收口与最终可行性方案

### 14.1 收口工作

1. 正式 default/challenger/managed ceiling 清单；
2. 清理失败/未消费实验 dependency、service 和 image；
3. legacy code 的 `implementation_lifecycle` 转为 compatibility/regression_only/retired；
4. 完成 archive/redirect/import/runtime consumer map；
5. 固定 lock、SBOM、license、security、deployment；
6. 备份/恢复/升级/rollback/exit runbook；
7. 运维、监控、成本和容量计划；
8. 最终 architecture、feasibility、migration、operations 文档；
9. Project OS、worklog、README、checklist、public docs 一致；
10. clean branch、exact staging、commit、non-force push；
11. fresh engineering/Evidence/report/product/security review；
12. Owner 决定产品版本和 release，不由程序自动推断。

`CLS-03` 的 legacy retirement 硬门为：historical implementation package discovery=0、active imports=0、Runtime Registry refs=0、current consumers=0、archive redirect/origin/digest complete、`verify_active_baseline.py` 与 clean-main proof 通过。rollback 只能重新启用已资格验证的薄 compatibility adapter，不能把 attempt-specific R3–R14 还原为活动实现。

### 14.2 完成定义

本程序只有在以下全部成立时才 complete：

- R14 已正确 strategic close，未假装 PASS；
- `R14-REPLACEMENT-S1-CLOSURE` 已 PASS 且 Owner 已明确处置 RC-S1-109/110；若仍 open，程序只能 partial/stopped；
- 旧规划已被当前程序和 ADR 正确 supersede；
- S1–S5 每个能力有 Build/Adopt/Hold/Retire；
- Adopt 能力有广泛 longlist、排除记录和 research saturation；
- 胜出组件已实际安装、固定版本、SBOM/license 和部署画像；
- Z 盘 lab 可复现；
- 当前分支已按目标架构集成；
- FIN domain kernel 与 vendor/framework 隔离；
- 旧代码有兼容、回归、退役和 rollback，历史实现不在默认 package/Runtime/API/UI/CI 主路径；
- 真实 case 和 DeepSeek 允许节点已验证；
- critical financial slice 无未解释重大错误；
- S1–S5、人审、报告、产品、运维、安全分别有 verdict；
- 没有隐藏失败、削弱 validator 或用 vendor benchmark 替代产品证明；
- Git/Project OS clean、同步、可恢复。

若某组件或产品门失败，可以形成 `program_terminal_status=partial/stopped` 的可行性结论，或 `capability_disposition=HOLD_TRIGGER`；不能把 held ticket 或 HOLD_TRIGGER 偷换成全程序 complete。

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
| H0 governance/source-doc/Project OS candidate 写入 | plan fresh PASS 后 exact allowlist true；不激活 Phase 1 |
| Phase 1 repo/data metadata 只读＋bounded audit artifact 写入 | valid H0＋G0 PASS receipt 后 true |
| Phase 2 官方来源网络调研 | false；valid G0 后仍须 exact RSH execution-authority receipt |
| Phase 3 qualification contract/evidence repo 写入 | false，QL candidate-contract authority receipt 前不允许；仅 qualification exact allowlist，禁止 production src/pyproject/current config/data |
| package/repo/model 下载 | false，QL candidate review＋execution-authority receipt 前不允许 |
| Z 盘 qualification install/service/local fixture run | false，QL execution-authority receipt 前不允许 |
| qualification-only index/data/shadow write | false，Phase 3 QL / Phase 5 MIG execution-authority receipt 与 exact root 前不允许 |
| qualification service stop/uninstall | false，install/start 前必须由同一 QL candidate contract 预授权；只在 exact stop/failure/expiry 消费 |
| failed/held qualification candidate artifact retire/delete | false，terminal result/rollback receipt、exact target manifest 与 evidence retention proof 前不允许 |
| unadmitted shadow artifact retire/delete | false，exact candidate/slice rollback receipt、target manifest 与 no-current/admitted-reference proof 前不允许 |
| migration candidate route/writer/exporter/feature switch stop/disable | false，MIG implementation/run 前必须由同一 slice contract 预授权；只在 exact stop/failure/expiry 消费 |
| unconsumed migration scaffold retire/delete | false，exact MIG rollback receipt 与 imports/registry/current-consumers=0 proof 前不允许 |
| Phase 4 ADR/migration registry write | false，Phase 1/2/3 PASS 前不允许 |
| Phase 5 src/test/config/lock implementation write | false，Phase 4 frozen＋exact MIG execution-authority receipt 前不允许 |
| dual-read compare | false，Phase 5 exact MIG execution-authority receipt 前不允许 |
| current consumer cutover | false，Phase 6 exact ACC-Sn terminal PASS＋downstream-activation receipt 前不允许 |
| 删除 D:\FIN_Insight_Agent\data\indexes | false，Phase 3 条件全部满足后才允许 |
| legacy source retire/delete | false，Phase 7 CLS-03 硬门前不允许 |
| R14 implementation/pre-formal/formal | false / permanently not on active route |
| R15/R16 | false |
| DeepSeek live | false，Phase 3/6 model execution-authority receipt＋TokenBudgetBasis 前不允许 |
| external source execution | false，单独 route execution-authority receipt 前不允许 |
| embedding execution | false，独立 QL-07 execution-authority receipt 前不允许 |
| retrieval engine/reranker execution | false，依次 QL-07→QL-08→QL-09 execution-authority receipt 前不允许 |
| Evidence admission | false，ACC-S1 execution-authority receipt 前不允许 |
| NumericFact/S2 authority | false，ACC-S2 execution-authority receipt 前不允许 |
| S3 research judgment | false，ACC-S3 execution-authority receipt 前不允许 |
| report candidate generation | false，ACC-S4-CANDIDATE execution-authority receipt 前不允许 |
| qualified-human S4 approval | false，ACC-S4 execution-authority receipt＋exact human gate 前不允许 |
| qualified-human product acceptance | false，ACC-S5 execution-authority receipt＋exact product-human gate 前不允许 |
| product/publication/release | false，ACC-S5 terminal PASS digest＋downstream activation＋Owner release receipt 前不允许 |

## 19. 计划冻结后的第一执行队列

严格顺序：

1. fresh、作者分离、只读审查本 plan-only commit；
2. 修复所有 P0/P1/P2，必要时新 plan-only revision；
3. 提交并推送 exact plan；
4. 创建 H0 Phase 0 candidate：物化 plan PASS receipt、machine manifest、source supersession、Project OS、worklog 和 machine-semantic test；H0 changed paths 必须排除本计划，H0 plan blob/raw SHA-256/bytes 必须等于 C0；
5. 对 clean exact H0 做 fresh read-only review；失败则保留 H0/failure receipt 并创建 successor；
6. 仅在 H0 review PASS 后创建 one-path G0 activation receipt，验证 H0 manifest 与 plan blob/raw SHA-256/bytes 均未变；
7. targeted verification、commit、non-force push，并由 machine test 计算 effective Phase0 PASS；
8. 只在 valid G0 后开始 Phase 1 bounded read/audit-write 和有独立 ticket 的 Phase 2 research。

本队列不包含 package install、模型调用、外源、formal、索引删除或生产迁移。

## 20. Plan review history 与 v1.4 修正

exact v1.0 commit `01ffc77b213899d3f177b13b1d38a43e390d3d0c`、tree=`7e8d5ee26d6c2947edec8e6690e11233c8e6d895`、plan blob=`3017dcc4a5e29af5298a26d42fa6de039722beb8` 经 fresh、作者分离、只读审阅得到 `PLAN_FAIL_REVISION_REQUIRED / P0-P1-P2-P3=0/5/2/0`。该失败保持不可变；v1.1 针对七项 finding 作出：

1. 完整逐动作 authority/domain-authority 状态机与 H0→G0 非自引用激活；
2. index 删除前 snapshot/restore 或 isolated rebuild 硬门、non-reproducible=0 与重解析/identity containment；
3. `R14-REPLACEMENT-S1-CLOSURE` 27,026/239/277/human-gold/原 gate/Owner 处置合同；
4. 独立 QL-07 embedding，再固定 embedder 比 QL-08 engine，最后 QL-09 reranker；
5. 完整历史实现移出 production `src`，compat 只留薄 shim；
6. Phase 2–7 stable ticket/slice registry；
7. W3/W4 拆成独立 feature switch/result/review/rollback 子 slice。

v1.1 另吸收真实 repo-surface 初查：package cycles、domain inversion、28-resource exact-digest spine、config/runner taxonomy 与 pytest marker 分类缺口。

exact v1.1 commit `3fc3dcf3d44984f702ce20d27a364bcd2229857e`、tree=`fcee84fe0c2164de4a3c0321595cbfd5a614a9d2`、parent=`01ffc77b213899d3f177b13b1d38a43e390d3d0c`、plan blob=`baaa86192ef07c15b1024d8307a15496fcedd861`、raw SHA-256=`63d8b0e060d2d65006ab05ab76c08b7abc27f3843eed434c180aa755a03035db`、bytes=`69343`，经作者分离、只读、对该 exact candidate 首次完整阅读的 reviewer 审阅得到 `PLAN_FAIL_REVISION_REQUIRED / P0-P1-P2-P3=0/2/0/1`。受协作树硬节点上限影响，该 reviewer 复用了一个此前未读写 v1.1 的既有只读任务身份，不冒充新的 fork-none 节点；其审阅前后 repo clean、origin aligned，且 writes/network/model/install/formal/old-live-state 均为 0。该失败保持不可变；v1.2 针对三项 finding 作出：

1. `h0_governance_materialization_write` 显式排除本计划；H0 与 G0 均强制保持 C0 plan blob/raw SHA-256/bytes 不变，计划行为、门、权限或接口变化只能走新的 plan-only `Cn`；
2. 增加独立 `phase3_qualification_contract_evidence_write`：candidate manifest 必须先于 download/install/run，qualification allowlist 与 production `src`/`pyproject.toml`/正式 lock/current config/data deny 明确分离，candidate/result/review/activation 不得互相覆盖；
3. 删除候选目标目录树中重复的 `tests/regression/`，只保留一个根并在其下承载 `legacy_r14/`。

exact v1.2 commit `e595d343cc1e7ffa75df2b2eee690a624430687e`、tree=`c1b36147e416bb88460f1d40300ef7d21b7fcf59`、parent=`3fc3dcf3d44984f702ce20d27a364bcd2229857e`、plan blob=`6af6227f6c0c8d697d4dfbcf06b8eda9672625b9`、raw SHA-256=`d300b8515ad04455ec26548fb642abc5507580803dafc5d84b4c0338dc7d7074`、bytes=`73688`，经作者分离、只读全量审阅得到 `PLAN_FAIL_REVISION_REQUIRED / P0-P1-P2-P3=0/1/1/1`。受协作树硬节点上限影响，该 reviewer 复用了参与过 v1.1 只读设计审计、但未参与 v1.2 写作的既有任务身份，不冒充新的 fork-none 节点；其审阅前后 repo clean、local origin-tracking ref aligned，且 writes/network/model/install/formal/delete/old-live-state 均为 0。该失败保持不可变；v1.3 针对三项 finding 作出：

1. 把 `ACC-S4-CANDIDATE` 注册为稳定票据并冻结 `ACC-S3 PASS → candidate authority → non-released result → S4 review/repair → ACC-S4 activation → ACC-S5` 的非自引用顺序；
2. 新增 `qualification_service_stop_uninstall`、`qualification_candidate_artifact_retire_delete`、`unadmitted_shadow_artifact_retire_delete`、`migration_slice_stop_disable` 与 `unconsumed_migration_scaffold_retire_delete`，为 fail-closed stop 和 W0/W3b/W3c/W4c 清理绑定 exact target、证据保留、pre/post receipt 与保护面 deny；同时把 W2/W5 改成始终不切 current consumer 的 shadow/candidate preview；
3. 将 P0-04 必须 supersede 的 current baseline/S0–S5 closeout plan 补入 Source index，并区分 P0-04 update set、continuity worklog、Project OS update set 与 read-only input set。

exact v1.3 commit `b1c961edde4689c18d12aee0db4260a5021b93cb`、tree=`d100ac1b9b4d455a224da1693e70da318628f464`、parent=`e595d343cc1e7ffa75df2b2eee690a624430687e`、plan blob=`7b068086801f815a0968c61c95835be7617f9947`、raw SHA-256=`6dd576b0cbbbda51cb49162e9b7b52ad91089989eb5b46b4f1ccfc4b2ed68fc3`、bytes=`81570`，经作者分离、只读全量审阅得到 `PLAN_FAIL_REVISION_REQUIRED / P0-P1-P2-P3=0/1/1/0`。受协作树硬节点上限影响，该 reviewer 复用了做过 v1.0 exact review 与 v1.2 H0 只读 materialization map、但未参与 v1.3 写作的既有任务身份，不冒充新的 fork-none 节点；其审阅前后 repo clean、local origin-tracking ref aligned，且 writes/network/model/install/formal/delete/old-live-state 均为 0。该失败保持不可变；v1.4 针对两项 finding 作出：

1. 冻结 phase、ticket lifecycle/terminal、downstream activation、action grant、program terminal、artifact immutability、implementation lifecycle 等独立原始状态轴；把 execution authority 与 terminal PASS 后的 downstream activation 拆成不同 receipt，compound labels 只允许做可重算 derived flags；
2. 修正 S4→S5 人工权限链：`ACC-S4-CANDIDATE` 先生成并审 report，`ACC-S4 execution_authority_receipt` 再授权 exact human decisions，human result/denominator/authority review 后才允许 ACC-S4 terminal PASS/downstream activation；`ACC-S5.predecessor` 绑定该 terminal digest/activation，另以 `qualified_human_product_acceptance` 完成 S5 human result，最后才可能 terminal PASS/release。

v1.4 必须重新形成 plan-only commit 并接受 exact、作者分离、只读全量审阅；本段不能自行关闭 v1.3 findings。

## 21. Source index

P0-04 supersession/update source set；H0 仍须把最终 exact changed-path allowlist 写入 machine manifest，不能由本节隐式扩大：

- docs/product/FIN_0_1_3_PRODUCT_CAPABILITY_BUILD_ADOPT_HOLD_RETIRE_AUDIT_20260830.zh-CN.md
- docs/product/FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md
- docs/architecture/research/FIN_0_1_3_MATURE_TECH_STACK_LANDSCAPE_AND_ADOPTION_DECISION_PACKET_20260830.zh-CN.md
- docs/architecture/repository/FIN_0_1_3_STRICT_MAINLINE_REBASELINE_ACCEPTANCE_AND_MIGRATION_PROGRAM_20260811.zh-CN.md
- docs/worklog/fin_0_1_3_s1/124_dell_03b_R14_program_level_architecture_execution_plan.md
- docs/worklog/fin_0_1_3_s1/128_dell_03b_R14_I2_corpus_parity_governance_correction_and_reaudit_pass.md

Phase 0 decision-continuity worklog append set：

- docs/worklog/fin_0_1_3_s1/129_product_capability_audit_and_mature_stack_decision_packet.md

P0-05 Project OS update set：

- docs/project_os/current_context_pack.zh-CN.md
- docs/project_os/capability_status_ledger.jsonl
- docs/project_os/root_cause_issue_ledger.jsonl

Phase 0 current-navigation/checklist materialization candidate set；只有 C0 PASS receipt 和 H0 manifest 的 exact allowlist 才能最终授权：

- docs/worklog/00_current_master_checklist.md
- docs/README.md
- docs/architecture/repository/README.md
- docs/product/README.md
- docs/worklog/README.md

只读事实输入；H0 没有新增对应外部证据或金融方法时不得为“看起来完整”而重复追加：

- docs/architecture/research/FIN_0_1_3_MATURE_STACK_RESEARCH_SNAPSHOT_MANIFEST_20260830.zh-CN.md
- docs/architecture/repository/FIN_0_1_3_CURRENT_BASELINE_CODE_MAP_20260811.zh-CN.md
- docs/project_os/README.md
- docs/project_os/external_pattern_registry.jsonl
- docs/project_os/financial_research_method_registry.jsonl
