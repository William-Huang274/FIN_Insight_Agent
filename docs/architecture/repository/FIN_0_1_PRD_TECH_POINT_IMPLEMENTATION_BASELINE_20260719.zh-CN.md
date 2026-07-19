# FIN 0.1 PRD / TECH / Point 实现基线

日期：2026-07-19

状态：`stage_review_baseline / internal_development_only / release_blocked`

产品复盘：`docs/product/FIN_0_1_STAGE_REVIEW_20260719.zh-CN.md`

代码主干与断连审计：`docs/architecture/repository/FIN_0_1_CODE_MAINLINE_ARCHIVE_AND_DISCONNECTION_AUDIT_20260719.zh-CN.md`

## 1. 目的

本文把 PRD、TECH_00/00A、TECH_01-11、FIN 0.1 ReleaseContract、Point 01-07、当前代码、测试和 release evidence 对齐为一个阶段基线。它回答四个不同问题：

1. 产品文档承诺了什么；
2. TECH owner 定义了哪些对象和 invariant；
3. Point / vertical train 实际交付到哪一层；
4. 哪些能力已经被当前 FIN 0.1 主路径消费并验证。

本文不将历史 R/S/P 文档、fixture 数量、页面入口或 contract test 自动等同于 current release capability。

## 2. Source of Truth 与时间边界

当前判定顺序：

1. 产品目标：PRD、Product Positioning、Release Ladder、FIN 0.1 FeatureScope；
2. owner/invariant：TECH_00、TECH_01-11；
3. 当前 release authority：ReleaseContract v1.2、backlog v1.1、vertical-train overlay；
4. 当前实现事实：代码、当前 tests、release evidence、capability ledger、root-cause ledger；
5. 工作过程：worklog，仅作事实轨迹，不覆盖前四项。

`fin_ia_0_1_feature_scope_matrix_v1_0.json` 的 `accepted_scope_implementation_not_started` 是 2026-07-17 的 immutable scope-freeze 状态，不是 2026-07-19 的实现进度。它的 feature IDs、surface 和 deferred boundary 仍有效；当前 implementation/release 状态由 v1.2 ReleaseContract 和本基线解释。

## 3. 当前实际系统

当前 FIN 0.1 主路径的实际结构是：

```text
React/Vite Workbench
  /next/tasks
  /next/cases/:id/run
  /next/cases/:id/evidence
  /next/cases/:id/workpaper
  /next/cases/:id/report
  /next/cases/:id/review
  /next/cases/:id/inspect
        |
FastAPI /api/v1
        |
Case / Planning / Execution / Evidence / Integrity /
Deliverable / LocalResearch / HumanBaseline services
        |
Point 01 RuntimeFacade + SQLite WAL + content-addressed ObjectStore
        |
P36 local research projection
  -> local RAG / SQL / Graph / official assets
  -> deterministic numeric / repair / judgment / writer
```

真实外部 model/tool/provider 不在默认页面加载或 test path 中。当前冻结的 DeepSeek runner 只写 `.codex_runtime`，并明确禁止 canonical Case write、evidence promotion、release admission 和自动重试。

## 4. TECH_01-11 当前成熟度

| TECH | Owner 范围 | 当前 FIN 0.1 实证 | 成熟度判断 | 主要缺口 |
| --- | --- | --- | --- | --- |
| `TECH_01` | ResearchCase、DecisionSurface、Gap/Repair、Workpaper、LeadReview 研究语义 | Case、10-cell DecisionSurface、planning checkpoint、Workpaper/LeadReview current-train path | `runtime_injected / scoped_consumed` | formal owner closeout、跨行业 calibration、same-Case Agent follow-up 未完成 |
| `TECH_02` | Agentic Search、EvidenceRequest、Tool Planner、SourceHunter、Evidence Gate | EvidenceRequest/candidate/gap/repair surface；31 条 local candidates；promotion 保持 0 | `runtime_partial / scoped_consumed` | live ToolGateway/SourceHunter、provider receipts、accepted promotion calibration 未完成 |
| `TECH_03` | source metadata、RAG/KB、graph、memory address/PIT | local RAG/SQL/Graph/official-asset read path 和候选 lineage | `runtime_partial` | institutional memory registry、permission-aware reuse、PIT replay 和 supersession 未统一进入当前链 |
| `TECH_04` | parser、NumericFact、MetricDefinition、NumericProgramTrace | 3 exact facts、2 derived margins、当前 Case numeric trace | `fixture_and_scoped_runtime_proven` | 完整 source/parser profile、unit/period/row negative corpus 和 formal promotion closeout 未完成 |
| `TECH_05` | Domain Judgment、counterevidence、WWC、cell projection | 10 deterministic judgments、counterevidence、WWC、remaining gaps | `scoped_deterministic_consumed` | DeepSeek Domain/Lead 未运行；human-calibrated judgment 与 research validity 未完成 |
| `TECH_06` | durable runtime、permission、state、budget、actor/accountability | Foundation Alpha contract/runtime proof；WorkUnit/cancel/activity/recovery；bounded write boundaries | `foundation_contract_runtime_proof_complete / operational_not_qualified` | entry-to-clean-child package identity 和 bounded operational vertical 未通过；production authority 保留 legacy |
| `TECH_07` | ContextEngine、skills、selection、compaction | 仓库有 context/method/skill runtime 资产；Writer input 已做 bounded whitelist | `runtime_partial / current_vertical_not_fully_demonstrated` | 当前 FIN 0.1 未证明每个 live/model node 都消费 exact role-specific context/injection plan |
| `TECH_08` | subagents-as-tools、Agent/Prompt/Skill registry、handoff | 结构化 handoff/role/pack 合同和历史 runtime 资产存在 | `contract_and_fixture_partial` | 当前 release vertical 主要是 service/deterministic pipeline，不是真实并行 subagent/model orchestration proof |
| `TECH_09` | Workbench、Trace、Review、Artifact、Release semantics | Evidence/Workpaper/Report/Review/Trace surfaces、HTML/Markdown、exact fixture review | `product_partial / scoped_consumed` | exact human DecisionAttestation=0；report 仍 deterministic fallback；跨格式完整一致性 deferred |
| `TECH_10` | eval、failure attribution、release gates、improvement | vertical-train tests、shadow review、RG2/RG5 evidence、blocked P07.5 decision | `runtime_partial` | RG1/RG3/RG4 未关闭；没有真实 user-value baseline 或 closed learning loop |
| `TECH_11` | Watchlist、monitoring、alert、longitudinal refresh | 仅 architecture/contract 和历史零散投影 | `deferred_not_runtime_for_FIN_0_1` | 明确属于后续 release，不应阻塞 FIN 0.1 |

结论：TECH owner 图覆盖已经相对完整，但 owner 文档的“覆盖完整”不等于实现完整。当前 release 真正消费较深的是 TECH_01/04/06/09 的 bounded subset；TECH_02/03/05/10 为当前纵向的 partial；TECH_07/08 尚未通过真实模型链证明；TECH_11 deferred。

## 5. Point 01-07 当前状态

### 5.1 状态总表

| Point | 规划定位 | 已实现 / 已验证 | 当前判定 | 仍未完成 |
| --- | --- | --- | --- | --- |
| `Point 01` | canonical control、DecisionSurface compiler、durable foundation、migration boundary | canonical models/store/facade、compiler/pack、fixture/shadow lifecycle、权限/预算/recovery、rollback；P01-G5 narrow scope decision | `POINT01_FOUNDATION_ALPHA_CONTRACT_RUNTIME_PROOF_COMPLETE` | P01-G2 single operational attempt failed and consumed；operational qualification deferred to RG1；不是 production complete |
| `Point 02` | AppShell、Task Center、Case/Objective、DecisionSurface、Activity | P02.0 freeze approved；Case create/list/open/reopen；browser shell；plan compile/revise/accept/return；bounded WorkUnit/cancel/activity；10-cell projection | `current_release_path_largely_implemented_internal` | formal Point owner closeout未签发；operational resume/retry/SSE 与跨行业 calibration 未完整证明 |
| `Point 03` | Evidence addressing、retrieval、repair | local EvidenceRequest/candidate path、31 candidates、Evidence Workbench、typed gaps、一次 bounded repair | `scoped_local_path_implemented` | live SourceHunter/tool/provider、broad retrieval calibration、formal P03.5 closeout 未完成 |
| `Point 04` | parser、numeric、evidence promotion | 3 exact facts、2 derived metrics、lineage、Numeric UI；0 false promotion in current candidate | `P36_scoped_numeric_path_implemented` | 广泛 parser profiles、negative corpus、canonical evidence promotion 和 formal P04.5 closeout 未完成 |
| `Point 05` | domain judgment、counterevidence、Workpaper、repair、LeadReview | 10 deterministic judgments、Workpaper、counterevidence/WWC/gaps、fixture LeadReview/WriterAdmission | `deterministic_internal_path_implemented` | 真实 Domain/Lead model、same-Case explanation、exact human calibration、formal P05 closeout 未完成 |
| `Point 06` | Writer no-source、artifact、review、provenance | deterministic no-source Writer、10-section deliverable、HTML/Markdown、exact fixture review、bidirectional Trace、Workbench Next | `deterministic_internal_path_implemented` | 真实 model Writer、true Lead synthesis、exact Human Review、formal P06 closeout 未完成 |
| `Point 07` | candidate freeze、dogfood、regression、value、rollback、release decision | P36 internal dogfood、SaaS/Bank structural regression、shadow Senior R2、RG2 pass、RG5 pass、blocked release decision | `P07_5_blocked_decision_recorded` | RG1、RG3、RG4 blocked；FIN 0.1 未 released |

### 5.2 为什么不能简单说 Point 02-06 complete

Point 02-06 的 current vertical 确实已经形成产品链，且不少 execution point 达到 fixture/full current-train stage；但原详设中的 owner-level closeout 还包含更宽的 calibration、真实 provider/model 或 human evidence。此前项目已明确把建设顺序改为 vertical release train，允许先完成当前用户路径，再把未被当前路径消费的 owner hardening 放入 backlog。因此本基线使用：

- `current release path implemented` 描述当前纵向；
- `formal owner closeout not issued` 描述 Point 全范围；
- 不以未做 owner hardening 反向否定当前产品增量；
- 也不以 current-train pass 冒充整个 Point 或 production complete。

## 6. Vertical Train 实际结果

| Train | 用户可见增量 | 当前结果 |
| --- | --- | --- |
| `VT0` | Point 02 contract/dependency set closure | P02.0 v1.1 approved，关闭 route/action/command/query/OpenAPI/owner set |
| `VT1` | 浏览器 Case -> Plan -> WorkUnit -> Evidence | current-train path delivered；刷新/重开和 typed state 有测试 |
| `VT2` | Evidence -> bounded repair -> Numeric -> Workpaper -> Lead | three-cell 后扩为 10-cell deterministic candidate；identity 和 restart recovery 有证据 |
| `VT3` | Writer no-source -> HTML/Markdown -> Review -> Trace | deterministic internal chain delivered；Writer source/tool=0 |
| `VT4` | candidate freeze、P36 dogfood、structural regression、rollback、release decision | candidate and product surfaces ready；release decision blocked by RG1/RG3/RG4 |

这说明“先按 Point 横向做完再集成”的顺序问题已经得到流程纠正；但 current train 仍大量使用 deterministic/fixture substitutions，下一阶段必须转向真实语义和人审，而不是继续扩合同。

## 7. 当前可核验资产

### 7.1 产品代码

- `apps/workbench/backend/api/v1/`：Case、planning、execution、evidence、integrity、deliverable、local research、human baseline API；
- `apps/workbench/backend/application/`：对应 application services；
- `apps/workbench/frontend/vite/src/app/WorkbenchNext.tsx`：新的 agent-first `/next` surface；
- `apps/workbench/frontend/vite/src/features/`：Task、Case、DecisionSurface、Evidence、Numeric、Workpaper、Deliverable、Activity、Human Baseline；
- `src/sec_agent/canonical_runtime/`：Point 01 canonical runtime、store、compiler、permission、budget、recovery 和 bounded execution contracts。

### 7.2 当前 exact candidate

```text
case_id: case_80fb19038ebf44f5ef7ad5b5
research_digest: aa792b86fa5aed152ba38352eec54b08b8ad5a3603a553c57a66260eb389b093
analysis_digest: 9d47aa3b29db35839dd6aea10974747777dbf72177e7e54db5c4c9fb4311ee50
10 cells / 6 mandatory families / 31 candidates
3 exact facts / 2 derived margins / 10 judgments / 10 writer sections
network/model/provider/tool/evidence promotion/canonical Case mutation: 0
```

### 7.3 DeepSeek execution freeze

```text
contract: fin_ia_0_1_p36_three_cell_deepseek_vertical_contract_v1_1.json
contract_digest: 0b532c336376ef8ecfe6f774b5854000a96f26f079dabe8f276817a127da47e1
input_digest: 737080b114fd8f9368238f711c8ea224035af13e4f4fee5e9e45e9b4ae66730b
scope: demand_signal / revenue_capture / thesis_counterevidence
budget: 1 provider preflight + 3 semantic calls
cost cap: USD 0.05
actual calls: 0
status: frozen_pending_explicit_paid_llm_approval
```

## 8. 测试与证据口径

当前仓库有大量 Point 01 和 FIN 0.1 contract/API/browser tests。与本阶段最直接相关的 suites 包括：

- Point 01 canonical/runtime/scope-closeout；
- Point 02 Case/planning/execution/frontend；
- Point 03 Evidence；
- VT2 integrity/numeric/workpaper；
- VT3 deliverable/review/trace；
- VT4 candidate/regression/release/rollback；
- durable frontend、Workbench Next、human baseline；
- DeepSeek three-cell freeze/call-accounting simulation。

测试通过只证明对应 suite 的 declared scope。尤其：

- contract/API tests 不等于 operational run；
- browser fixture E2E 不等于 human product value；
- shadow Senior R2 不等于 exact Human Senior acceptance；
- deterministic writer 不等于 model report quality；
- rollback drill 不等于 production cutover admission。

## 9. 当前已知 release blockers

### 9.1 `RG1_vertical_path`

Point 01 的 single operational attempt 已 fail-closed 并消费 receipt。exact package 从 entry 到 clean-child 的 identity 未证明，actual/oracle/reviewer/Workbench 结果缺失。该失败不得改写为 pass，也不得自动重试。

### 9.2 `RG3_research_outcome`

shadow Senior R2 只证明当前 deterministic candidate 达到 `R1_artifact_complete`，没有关闭 `R2_research_valid`。三个 bounded gaps 仍在：advanced packaging specificity、semicap freshness、company-to-segment profit attribution；最关键的是 exact human Lead/Senior review 缺失。

### 9.3 `RG4_review_product_value`

Human Baseline API/UI 已实现，但当前 session=0。time-to-source、time-to-numeric-verify、weakest-judgment identification、writer review time、usefulness 和 reviewability 没有真实观测。

### 9.4 报告 synthesis / projection

当前 `/next/report` 消费 deterministic local writer，并把第一个 judgment 作为核心答案。它是可检查 fallback，不是最终 Lead synthesis。真实模型 artifact 还未生成，也未投影到 Workbench。页面必须继续明确 mode/digest/boundary，不能让用户误以为这是模型完成的完整报告。

## 10. Git 与变更边界

当前 worktree 含大量既有 staged/working/untracked 变更，覆盖 Point 01、FIN 0.1 和历史资产。本次复盘不重置、不重新分组、不 stage，也不以 `git diff --stat` 的总体规模推断单项功能成熟度。后续发布候选必须单独冻结 exact file/config/schema/test manifest；当前工作树不是 release candidate commit。

## 11. 下一执行顺序

1. 保持当前 deterministic fallback 可回滚，并在 Report/Inspect 明示它不是 model/human accepted output。
2. 由用户作一次显式 paid-run 决策；若批准，仅执行已冻结的 1+3 DeepSeek calls。
3. 校验 exact model artifact、调用/费用/停止计数，并只读投影到 `/next`。
4. 用户完成 exact Human Senior Review 和 analyst/senior task baseline，形成 RG3/RG4 证据。
5. 仅当 Human Review 要求时，对两个 freshness/specificity gap 做最多一次 bounded source substitution；profit attribution 允许保留 cannot-infer。
6. 将 RG1 作为单独产品/运行风险决策，不与模型质量或 UI repair 混在一起。
7. P07.5 对同一个 exact candidate 重算 RG1-RG5，签发 release 或 blocked decision。

下一阶段禁止默认扩展：新 Point、新 gate family、broad provider matrix、商业数据、生产 cutover、全行业 pack 或新的防御性治理项目。
