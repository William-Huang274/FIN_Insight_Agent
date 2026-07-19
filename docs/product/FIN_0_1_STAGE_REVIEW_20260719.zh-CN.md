# FIN 0.1 PRD / 产品阶段复盘

日期：2026-07-19

状态：`internal_development_candidate / release_blocked / production_not_admitted`

适用范围：`REL-PROD-001 / FIN 0.1 Internal Alpha`

技术与 Point 实现基线：

- `docs/architecture/repository/FIN_0_1_PRD_TECH_POINT_IMPLEMENTATION_BASELINE_20260719.zh-CN.md`
- `configs/releases/fin_ia_0_1_release_contract_v1_2.json`
- `reports/release_evidence/fin_ia_0_1_vt4_p07_5_release_decision_v1_0.json`

## 1. 阶段结论

FIN 0.1 已经不是只有 PRD、TECH 和后端对象的空壳。当前仓库存在一条可以在浏览器中查看和操作的内部研究纵向链：

```text
ResearchCase
 -> 10-cell P36 DecisionSurface
 -> 31 条本地真实候选证据
 -> 3 个 exact facts + 2 个 derived margins
 -> bounded repair
 -> 10 个 deterministic judgments / Workpaper sections
 -> fixture LeadReview / WriterAdmission
 -> no-source deterministic Writer
 -> Workbench / Report / Review / Trace
```

但这条链的当前成熟度是“本地真实资料 + 确定性内部分析 + fixture/shadow/internal 产品界面”，不是完整 Agent 产品发布：

- 已实现可持续运行的 React/Vite Workbench Next，默认中文，旧界面保留回滚；
- 已实现当前 P36 Case 的本地 RAG/SQL/Graph/official-asset 候选、数字、底稿、报告和 trace 投影；
- 已完成内部 fixture dogfood、结构回归和 bounded rollback；
- 尚未运行本轮冻结的 DeepSeek 三-cell Domain/Lead/Writer 纵向，实际 `model_calls=0`；
- 尚无 exact Human Senior Review，human baseline session 数为 0；
- Point 01 的 operational attempt 失败证据仍然保留，RG1 未通过；
- `P07.5=FIN_0_1_INTERNAL_ALPHA_BLOCKED`，没有发布，也没有 production admission。

因此当前最准确的产品定义是：

> FIN 0.1 已形成可供内部研究和产品验证的纵向开发候选，但研究质量、真实人审价值和 operational qualification 尚未完成，不能称为已发布 Internal Alpha。

## 2. 原始产品承诺

PRD 将 FinSight 定位为 `Institutional Research Control and Memory System / AI-native Research Management System`，不是一次性报告生成器，也不是通用金融聊天页。FIN 0.1 消费其中的首个 bounded vertical：

- `B0` 产品壳与任务闭环；
- `B2` 公司深度底稿；
- `B3` 产品、竞品和供应链 bounded subset；
- `B7` DecisionSurface、Evidence、Numeric 和 targeted repair。

目标用户是内部 analyst 和 senior reviewer。目标 Job-to-be-Done 是在一个持久 ResearchCase 中完成创建、计划、执行、证据和数字复核、底稿、repair、LeadReview、内部报告、exact-version human review 与 provenance 回溯，而不是只得到一段回答。

FIN 0.1 的产品范围仍是 `P001-F01` 到 `P001-F15`，P36 六个产业链 family 只是 Anchor Case calibration coverage，不是产品功能列表。

## 3. 成熟度口径

本复盘使用以下口径，避免把页面、fixture 或历史资产写成完整能力：

| 状态 | 含义 |
| --- | --- |
| `implemented_internal` | 当前 FIN 0.1 浏览器和 API 主路径可用，并有当前版本测试或浏览器证据 |
| `implemented_scoped` | 当前 P36/local/fixture 范围可用，尚未证明跨来源、跨 Case 或完整 owner closeout |
| `partial` | 有产品 surface 或一段纵向实现，但缺少当前合同要求的关键动作、真实执行或验收 |
| `frozen_pending_execution` | exact contract/input 已冻结，但实际模型、网络或 operational 执行尚未发生 |
| `deferred` | 明确不属于 FIN 0.1 release gate |
| `blocked` | 当前 release gate 缺失，不能发布 |

## 4. F01-F15 当前实现矩阵

| Feature | 产品承诺 | 当前已实现 | 当前判断 | 未完成 / 不得误写 |
| --- | --- | --- | --- | --- |
| `F01` Dashboard / Task Center | 创建、搜索、打开 Case，查看 stage、失败、待审和成本状态 | 浏览器 Task Center、Case 列表/创建/打开、真实当前 Case 摘要、typed empty/error state | `implemented_internal` | 不是多租户生产 dashboard；成本只显示已有计数 |
| `F02` ResearchCase / Objective | 持久 Case identity、objective、as-of、version、reviewer 和边界 | Case API、SQLite/ObjectStore 持久化、刷新/重开、versioned plan/objective | `implemented_internal` | 真实客户 Case 和 production authority 未启用 |
| `F03` Dynamic DecisionSurface | 10-20 cells、六类 mandatory families、planning checkpoint、可修订计划 | 当前 P36 10 cells / 6 families；计划编译、修订、接受/退回 API/UI 已进入 current train | `implemented_scoped` | 当前 clean candidate 是 10 cells；未形成跨行业的正式 Point 02 calibrated owner closeout |
| `F04` Durable execution | WorkUnit/Attempt、cancel、resume/retry、checkpoint、typed stop 和 Activity | bounded fixture WorkUnit、cancel、typed stop、Activity、刷新与 backend restart 恢复 | `partial` | operational execution 未 qualified；当前产品主链没有完成真实 resume/retry worker 证明 |
| `F05` Agentic Search | EvidenceRequest 驱动 RAG/SQL/Graph/market/official SourceHunter 和 bounded fallback | 本地真实资产检索得到 31 candidates；包含 local RAG/SQL/Graph/official-asset lanes | `implemented_scoped` | 没有本轮 live SourceHunter、外部 tool/provider 或真实 Agent 搜索循环；调用计数为 0 |
| `F06` Evidence Workbench | candidate/accepted/rejected/gap/source authority/citation、reject/request repair | Evidence Matrix/Workbench、候选检查、typed gaps、reject/request repair、一次 deterministic repair | `implemented_scoped` | `evidence_promotion=0`；未证明 live provider breadth 或正式 promotion closeout |
| `F07` Numeric / Fact audit | exact row/entity/period/unit/scale/coordinate 和可复算公式 | 3 exact company facts，2 个可复算 margin（74.99% / 62.42%），numeric lineage 可查看 | `implemented_scoped` | 只证明当前 P36 local subset；未覆盖完整 parser/source profile 和负例校准 |
| `F08` Workpaper / Domain Judgment | 按 decision cell 形成 judgment、counterevidence、WWC 和 evidence/gap binding | 10 个 deterministic judgments、10-section Workpaper、反证、WWC、repair 和 remaining gap 投影 | `partial` | 不是 paid/model-calibrated domain judgment；exact human Senior R2 未完成 |
| `F09` Gap / Repair Queue | GapRecord、RepairTicket、source-owner routing、attempt 和 bounded stop | request repair、一次 official-policy deterministic repair、typed stop/gap 展示 | `partial` | 尚不是通用 live source-owner repair queue；未完成 full owner-level lifecycle 校准 |
| `F10` Lead Review / Writer Admission | 跨 cell coverage/conflict/story review，冻结 exact WriterBrief | exact fixture LeadReview/WriterAdmission 和 digest binding 已存在 | `partial` | 当前不是实际 DeepSeek Lead，也不是 exact human LeadReview；模型纵向仍待批准 |
| `F11` Internal Deliverable | no-source Writer、HTML/Markdown、version/hash parity | deterministic no-source Writer、10 sections、HTML/Markdown/报告页和 source access=0 | `partial` | 当前报告仍是 deterministic fallback；核心答案取首个 judgment，不是完整 Lead synthesis，不能当 decision-ready report |
| `F12` Human Review / Accountability | 对 exact target/version/hash comment、return、repair、accept | Human Baseline API/UI、exact digest attestation、草稿恢复和 review decision surface | `partial` | 当前 session=0、exact human review=0；只有 surface，没有真实验收结果 |
| `F13` Provenance / Trace | claim/source/numeric/repair/gap 双向 lineage | 当前 fixture candidate 的 material claim Trace、source-to-claim 和 claim-to-source 浏览器投影 | `implemented_scoped` | 只证明当前 candidate；不是跨所有来源和 artifact 的 production lineage |
| `F14` Same-Case explanation | 对当前 Case 追问 why/gap/WWC，复用冻结上下文并 bounded stop | UI/合同中保留 follow-up 与 bounded follow-up 字段 | `partial` | 没有完成一次 Agent same-Case explanation 主流程；当前 Human Review follow-up 字段不等于该能力 |
| `F15` Quality / Release Feedback | 显示 R level、blocker、known gap、成本、rollback 和 RG1-RG5 | release evidence、shadow Senior R2、RG2 fixture pass、RG5 rollback pass、blocked release decision | `partial / blocked` | RG1、RG3、RG4 未通过；不得写成 FIN 0.1 released |

## 5. 用户今天实际能做什么

在当前本地开发环境，用户可以：

1. 从 `/next/tasks` 创建、搜索、打开并重开 ResearchCase；
2. 在 Case 中查看研究目标、运行状态、10-cell P36 研究结构和本地候选；
3. 在 Evidence 页面检查 31 条当前候选、来源、摘录、边界和 gaps；
4. 在 Workpaper 页面查看数字、判断、反证、repair、WWC 与待补事项；
5. 在 Report 页面查看 deterministic internal draft；
6. 在 Review 页面按 exact digest 记录 analyst / senior baseline 输入；
7. 在 Inspect/Trace 页面检查结构化运行事件和 lineage；
8. 切换中文/英文，并保留旧 `/tasks` 作为回滚入口。

当前用户还不能把以下事项视为已完成：

- 运行真实 DeepSeek Domain/Lead/Writer 并查看其 exact artifact；
- 运行 live external search/tool/provider 或商业数据；
- 在主界面实际选择并执行模型、plugin、skill、knowledge graph 和 orchestration profile；当前只读配置摘要不是运行控制器；
- 得到一份经模型 synthesis 和 Human Senior 接受的 decision-ready 报告；
- 证明产品节省时间或降低 review burden；
- 完成 RG1 operational run、FIN 0.1 release 或 production cutover。

## 6. Agent 主功能是否做完

没有。

更准确的说法是：Agent 产品的“对象、控制面、本地数据链和审阅界面”已经形成较完整的内部骨架，当前 P36 的 deterministic vertical 可以运行；但决定产品价值的三层仍未关闭：

1. **真实语义执行层**：本轮 DeepSeek Domain/Lead/Writer 仅完成 exact input、预算和 fail-closed runner 冻结，尚未调用。
2. **真实研究质量层**：shadow Senior R2 只给出 conditional 结论；advanced packaging、semicap freshness、company-to-segment profit attribution 仍保留 gap，exact human review 缺失。
3. **真实运行与发布层**：Point 01 operational identity 传播未证明，RG1 blocked；RG3/RG4 也 blocked。

历史 R-series、S-series、P30-P37 中确实存在更多 agent、retrieval、graph、context、eval 和 Workbench 资产，但只有被当前 ReleaseContract 消费并经过当前纵向证据验证的部分，才计入 FIN 0.1 已实现能力。

## 7. Release Gate 当前状态

| Gate | 当前状态 | 证据与含义 |
| --- | --- | --- |
| `RG1_vertical_path` | `blocked` | entry -> adapter -> subprocess -> clean-child exact package identity 未证明；bounded operational vertical 未运行；actual/oracle/reviewer/Workbench artifact 缺失 |
| `RG2_evidence_numeric_integrity` | `pass_internal_fixture_candidate` | 当前 deterministic candidate 为 0 false promotion、material numeric trace 100%、writer source/tool 0；只限内部 candidate |
| `RG3_research_outcome` | `blocked` | shadow review 完成但 R2 未关闭；exact human Senior Review 缺失 |
| `RG4_review_product_value` | `blocked` | 产品界面就绪，但 human task baseline session=0，没有 time/review burden/value 观测 |
| `RG5_release_rollback` | `pass_bounded_internal_fixture` | 新 lane fail-closed，旧入口可回滚，canonical audit history 保留 |

`P07.5` 已签发的是 blocked decision，不是 release：

```text
FIN_0_1_INTERNAL_ALPHA_RELEASED = false
release_admission = not_issued
production_readiness = not_admitted
legacy_global_authority = retained
```

## 8. 当前主要产品债务

### 8.1 必须在 FIN 0.1 release 前关闭

1. 执行或明确放弃已冻结的 DeepSeek 三-cell真实语义纵向；若执行，必须保持 1 次 provider preflight + 3 次 semantic calls、USD 0.05 cap、无自动重试。
2. 将 exact model artifact 投影到 Workbench，并明确显示 `model / deterministic fallback / source boundary / digest`，不能继续把 fallback 当最终报告。
3. 完成一次 exact Human Senior Review 和一轮 analyst/senior product baseline，取得 RG3/RG4 事实。
4. 对 shadow review 的 bounded research gaps 作保留或最多一次受限补源，不扩成 broad source project。
5. 单独决定是否授权 RG1 bounded operational vertical；失败后仍 fail-closed，不进入循环 repair。
6. 由 P07.5 对 exact candidate 重跑 RG1-RG5 并作发布或继续阻断决定。

### 8.2 不应阻塞 FIN 0.1 的 deferred 能力

- Data Room、私有/授权数据和 OCR 全链；
- Watchlist、monitoring、R4 refresh；
- Research-to-Quant；
- 全行业 Sector Packs；
- PPT/Word/Excel/PDF 全格式一致性；
- 企业 SSO/SCIM/OA/KMS/DLP、多租户；
- 完整估值、预测和情景引擎；
- 实时行情、完整衍生品和商业数据；
- 自动交易或投资建议。

## 9. 下一阶段建议

下一阶段不再横向补 TECH 或创建新 gate，按一条真实用户纵向收口：

```text
truthful report state
 -> explicit paid-run decision
 -> exact DeepSeek 3-cell artifact
 -> Workbench projection
 -> exact Human Senior Review
 -> human task/value baseline
 -> bounded source follow-up only if review requires
 -> separate RG1 decision
 -> P07.5 release decision
```

阶段目标不是 production-grade 完备，而是回答两个产品问题：

1. 真实 analyst/senior 是否愿意反复使用这条研究链？
2. 在保留证据、数字、gap 和人工责任的前提下，真实模型是否比当前 deterministic fallback 明显提高研究判断和报告质量？
