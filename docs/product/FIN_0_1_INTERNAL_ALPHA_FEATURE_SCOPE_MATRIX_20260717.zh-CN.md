# FIN 0.1 Internal Alpha 产品功能范围矩阵

日期：2026-07-17
状态：`accepted_release_scope / implementation_in_progress_internal_only / release_blocked`
适用版本：`REL-PROD-001 / FIN 0.1 Internal Alpha`

> **2026-07-19 implementation overlay**：本文的 `P001-F01`-`F15`、surface、acceptance 和 deferred boundary 继续有效；机器文件 v1.0 中的 `implementation_not_started` 是 2026-07-17 immutable scope-freeze 快照，不是当前实现进度。当前已实现/部分实现/阻断状态见 `FIN_0_1_STAGE_REVIEW_20260719.zh-CN.md`。当前 release 仍为 `FIN_0_1_INTERNAL_ALPHA_BLOCKED`，`production_readiness=not_admitted`。

## 1. 范围纠正

FIN 0.1 不是“生成一份 P36 报告”的单功能版本。它是 PRD 中 `B0 产品壳与任务闭环 + B2 公司深度底稿 + B3 产品/竞品/供应链 bounded subset + B7 DecisionSurface/Evidence repair` 的首个内部纵向产品切片。

P36 的 accelerator、server OEM、foundry/advanced packaging、HBM、semicap 和 cross-chain counterevidence/What-Would-Change 是 Anchor Case 的六个必选 `cell families`，用于校准产品是否覆盖关键产业链机制；它们不是产品功能列表，也不要求 runtime 永久硬编码为六个 cells。

本版本的完整用户工作是：

```text
创建 ResearchCase
 -> 审阅并确认研究计划 / DecisionSurface
 -> 观察可暂停、可恢复的研究执行
 -> 检查证据、数字、缺口和工具尝试
 -> 审阅按判断问题组织的 Workpaper
 -> 对具体 cell/claim 发起 targeted repair
 -> Lead 完成跨 cell 审核并冻结 WriterBrief
 -> Writer no-source 生成内部交付物
 -> Senior 对 exact version 批注、退回或接受
 -> 从结论回溯到 cell、证据、数字程序和工具 observation
```

## 2. 目标用户与完成定义

目标用户：内部投研 analyst、senior reviewer。

目标 Job-to-be-Done：用户能够在一个持久 ResearchCase 中完成一次可审阅的 AI infrastructure 深度研究，而不是只得到聊天回答。系统需要减少任务拆分、重复查数、证据整理、数字复核、底稿编排和引用追踪的人工劳动，并保留人工裁决权。

`L2_internal_dogfood_pass` 最低定义：

- analyst 不编辑底层 JSON 即可创建并推进任务；
- senior 可以在同一工作台理解判断、证据、反方、缺口和修改历史；
- 至少一个真实 Anchor Case 达到 `R2_research_valid`；
- 失败、证据不足和商业数据缺口以 typed state 暴露，而不是生成貌似完整的答案；
- 产品有可执行 rollback，且不宣称 production readiness。

## 3. 用户可见产品范围

| Feature ID | 用户能力 | FIN 0.1 具体范围 | 主要产品 surface | PRD 来源 | TECH owner | 发布验收 |
| --- | --- | --- | --- | --- | --- | --- |
| `P001-F01` | Dashboard / Task Center | 创建、搜索和打开任务；查看 stage、失败原因、待审项、耗时和模型/工具预算摘要 | Dashboard、Task Center | 6.1、6.2、B0、9.1 | TECH_01、06、09 | 用户 5 分钟内创建任务；失败有原因和 next action |
| `P001-F02` | ResearchCase / Objective | 保存原问题、研究对象、as-of、语言、输出目标、source policy、reviewer、预算和 Case version | Case Overview | 4.0、4.1、6.2、B0 | TECH_01、06 | Case identity/version 可恢复；不能退化为一次 chat/run |
| `P001-F03` | Plan / DecisionSurface | Lead 用 universal archetype + AI infra sector pack + case delta 编译 10-20 个 cells；用户可审阅、增删、裁剪或退回计划 | Plan、Decision Surface | 4.1.1、4.2.1、6.2、B7、9.7 | TECH_01、05、07、08 | 每个 cell 有 owner、EvidenceSlots、禁止替代、stop rule；六个 anchor families 有覆盖 |
| `P001-F04` | Durable execution | 展示 workstream、WorkUnit/Attempt、tool/model stage、checkpoint、typed stop；支持 cancel、targeted retry/resume | Activity / Run Timeline | 4.1、7.8、9.7 | TECH_06、08、10 | 至少一次中断恢复和一次局部 retry；不要求生产级队列/SLA |
| `P001-F05` | Agentic Search | EvidenceRequest 驱动 RAG、SQL、graph、market pack 和 official-first SourceHunter；允许 neighbor/section/table expansion 与 bounded fallback | Evidence Search Activity | 7.3-7.7、B7、9.7 | TECH_02、03、06 | 每次调用有 ToolUseLedger；无结果时产生 typed exhaustion/gap，不直接写判断 |
| `P001-F06` | Evidence Workbench | 按 cell 查看 candidate、accepted、context-only、rejected、typed/commercial gap、source authority、citation、supplement 边界 | Evidence & Sources | 6.4、B7、9.4、9.7 | TECH_02、03、09 | 用户能手动 reject/request repair；supervisor supplement 不冒充 runtime evidence |
| `P001-F07` | Numeric / Fact audit | 展示 exact fact 的 entity、period、unit、scale、row/column/table lineage；展示 growth、margin、bridge、multiple 的公式与复算 | Numeric Drawer / Fact Table | 5.1、6.5、B2、B7、9.4、9.7 | TECH_04、09 | 100% material numbers 可复算；parser/row ambiguity 可见；零已知单位/期间错配 |
| `P001-F08` | Workpaper / Domain Judgment | 按 decision cells 组织业务/产品、财务、客户/供应链、竞争、资本/price-in、估值边界、风险、counter-thesis 和 WWC | Workpaper | 6.5、B2、9.2 | TECH_05、07、08、09 | 每个核心判断有 evidence refs 或 gap；不是 evidence dump |
| `P001-F09` | Gap / Repair Queue | 对 evidence、parser、numeric、domain、storyline 或 presentation gap 建 RepairTicket；路由到来源 owner；展示 attempt 和 stop | Repair Queue | 4.1.1、6.4、7.2、9.1、9.7 | TECH_01、02、05、06、08、09 | 至少一条真实 targeted repair 关闭或 attempt-backed stop；Writer 不承担补源 |
| `P001-F10` | Lead Review / Writer Admission | Lead 检查 coverage、跨 cell 冲突、反方、故事线、writer boundary；冻结 DecisionSurfacePack 和 WriterBrief | Lead Review | 4.1、7.1-7.2、9.5、9.7 | TECH_01、05、09 | Lead 在 planning/review 两处出现；存在 hard omission 时 Writer fail-closed |
| `P001-F11` | Internal Deliverable | Writer 只使用冻结 pack 生成内部 HTML 与 Markdown；表格/图表只引用 approved numeric refs；支持版本保存 | Deliverable | 6.8、B0、B2、9.3、9.7 | TECH_09 | Writer source/tool calls=0；HTML/Markdown 可打开并语义一致；PPT/Excel/PDF 非首版 gate |
| `P001-F12` | Human Review / Accountability | reviewer 可在 cell、evidence、number、claim、artifact 上 comment、return、request repair、accept；记录 actor、时间、target 和 exact version | Review Queue / Comments | 6.10、6.13、9.5 | TECH_06、09 | 至少一轮真实 review；artifact hash 与 review target 一致；不要求 OA/SSO |
| `P001-F13` | Provenance / Trace | 双向查询 claim -> cell -> evidence -> tool/observation -> parser/numeric -> promotion -> verifier，以及 source 影响哪些 claims | Trace Explorer | 4.1.2、6.4、9.4、9.7 | TECH_03、04、06、09 | 100% material claims 有 lineage 或明确 gap；拒绝项也有原因 |
| `P001-F14` | Same-Case explanation | 在当前 Case 内追问“为什么、哪里缺证据、什么会改变判断”，复用冻结 CaseControlMemory/DecisionSurfacePack；不做跨季度自动 refresh | Case Follow-up | 4.1.1、6.12、9.7 | TECH_01、03、07 | 一次 bounded follow-up 可回答并保持 source/as-of；R4 memory/monitoring 后置 |
| `P001-F15` | Quality / Release Feedback | 显示 Anchor 的 R level、hard blockers、known gaps、review edits、time/tool/model baseline 和 rollback result | Quality / Release Summary | 9.0、10、15 | TECH_10、06、09 | RG1-RG5 可复核；不得把 fixture/legacy/manual supplement 写成 FIN 0.1 能力 |

## 4. 首版工作台信息架构

首版不需要先做完整客户级视觉系统，但必须存在可操作的产品 surface，而不只是 JSON/API：

```text
Dashboard / Task Center
  -> New Research Task
  -> ResearchCase Workspace
       1. Overview & Plan
       2. Decision Surface
       3. Evidence & Numbers
       4. Workpaper & Repair
       5. Deliverable & Review
       6. Activity & Trace
```

允许内部 alpha 使用朴素 UI，并保留 JSON/API 作为调试和 replay surface；不允许只交付 JSON/API 后宣称 `L2_internal_dogfood_pass`。

### 4.1 前端产品合同

FIN 0.1 包含正式的内部前端建设，不是“后端先做完、最后再套页面”，也不是把现有 JSON、日志或生成 HTML 当成产品工作台。首版前端必须让 analyst/senior 在浏览器内完成下列动作：

1. 创建、搜索、打开和恢复 ResearchCase；
2. 审阅、编辑、退回或接受 Objective/DecisionSurface plan；
3. 启动、取消、局部 retry/resume，并看到 workstream/attempt/typed stop；
4. 查看 evidence、numeric、gap、citation 和 provenance，并执行 reject/request repair；
5. 审阅 Workpaper、LeadReview、WriterAdmission 和 exact artifact version；
6. comment、return、request repair、accept，并发起一次 bounded same-Case follow-up。

前端至少要显式处理 `loading / ready / running / awaiting_review / typed_gap / failed_with_next_action / stale / superseded` 状态。失败不能只进入浏览器 console；用户必须看到失败原因、影响对象和 next action。

首版采用 desktop-first，保证 1024px 以上工作区可用；移动端和客户级 design system 不是 release gate。视觉可以朴素，但信息层级、表格密度、筛选、状态、审阅动作和长内容阅读必须达到内部分析师可持续使用的标准。

## 5. Anchor Case 编译规则

P36 AI infrastructure 采用动态 DecisionSurface：

- cell 数量：10-20，目标 12-16；
- 固定的是研究责任和六个必选 `cell families`，不是固定标题或固定六格；
- Lead 可按本次问题合并、拆分或增加少量 case-specific cells；
- planning checkpoint 允许 reviewer 修改计划；
- risk/counterevidence/What-Would-Change、material numeric sanity 和 writer boundary 不得静默删除。

必选 families：

1. accelerator demand / value capture / concentration；
2. server OEM order/revenue quality / margin / cash conversion；
3. foundry and advanced packaging capacity / capex / bottleneck rent；
4. HBM demand / supply / pricing / customer concentration；
5. semicap capex read-through / lag / cycle / export policy；
6. cross-chain counter-thesis / price-in / What-Would-Change。

Enterprise AI/SaaS 和 US Banks 只用于验证 universal archetype、sector pack、period/metric policy 和 gap boundary，不能把 WorkBuddy 的事实、数字、估值或搜索策略编译进 runtime。

## 6. Agent 与数据能力边界

### 6.1 必须实际进入纵向链

- Lead Controller：计划、派单、状态裁决、跨 cell review、repair triage；
- Evidence Layer：RAG/KB、SQL、graph、market pack、SourceHunter 和 Tool Registry/Planner/Gate；
- Parser/Numeric：table/row/unit/period/scale、派生指标和 NumericProgramTrace；
- Domain operators：Product/Industry、Fundamental、Market/Capital、Risk/Counterevidence；
- ContextEngine 和 subagent-as-tools：role-specific context、结构化 handoff；
- Writer/Presentation：no-source、内部语言和表格/图表投影；
- Verifier/Workbench：claim、numeric、gap、artifact 和 review gate。

### 6.2 本版本数据范围

- 现有 SEC/IR 与公开披露；
- 现有结构化财务 SQL/exact-value ledger；
- 现有 RAG/KB、DocumentMetadataIndex 与 neighbor/section/table expansion；
- 现有 relationship/Product graph，按候选/关系/机制边界使用；
- 现有低频 market/capital/ownership/macro packs，明确 proxy、滞后和覆盖边界；
- 受限 official-first web/SourceHunter repair；
- P36 supervisor supplement 仅作为 `not_runtime_evidence` repair fixture。

不要求 FIN 0.1 完成所有 source provider、所有 PDF/parser profile、商业 consensus、实时资金流、完整期权/CDS 或全行业数据基座。

## 7. 首版不实现但必须预留接口

| Deferred | 原因 | 目标版本/轨道 |
| --- | --- | --- |
| Data Room、私有/授权数据、OCR 全链 | 需要 tenant/license/permission/retention 独立准入 | FIN 0.5 |
| Watchlist、定时刷新、alert、R4 memory | 需要长期 Case、stale propagation 和 notification | FIN 0.3 后 |
| Research-to-Quant、backtest、paper trading | 是独立 assisted workflow，不应挤占首个深研闭环 | 实验轨 / 后续 release |
| 全行业 Sector Packs | 首版只证明 pack compiler 和两个结构回归 | FIN 0.4 |
| PPT/Word/Excel/PDF 全格式一致性 | 首版先证明 canonical content + HTML/Markdown | FIN 0.3/0.5 |
| 企业 SSO/SCIM/OA/KMS/DLP、多租户 | internal alpha 不具备 production admission | FIN 0.5 |
| 完整估值/预测/情景引擎 | FIN 0.1 只允许可复算的 bounded derived metrics 与 price-in 判断 | 后续建模 slice |
| 实时行情、完整衍生品、商业数据 | 数据授权、成本、频率和覆盖独立决策 | 数据/市场扩展轨 |
| 自动交易或投资建议 | 明确非目标 | 不进入当前产品路线 |

## 8. Release Scope Gate

以下任一项缺失，FIN 0.1 不得仅凭 P36 memo 质量发布：

1. Task Center/Case workspace 无可操作入口；
2. DecisionSurface 无 planning checkpoint 或仍硬编码为六格；
3. 证据、数字、gap、repair 只能在日志/JSON 中查看，senior 无 review surface；
4. 没有 Workpaper 层，specialist 输出直接进入 Writer；
5. Writer 可补源或无法证明 source/tool call 为零；
6. reviewer action 未绑定 exact target/version/hash；
7. material claim 无 provenance；
8. Anchor 达到 R2，但未证明用户工作时间、review burden 或重复劳动得到首版改善。

## 9. Traceability

上游产品合同：

- `PRD_20260628_b2b_financial_research_workbench.zh-CN.md`：4、6、7、8.1、8.3、8.8、9、15；
- `PRODUCT_20260717_release_ladder_and_cadence.zh-CN.md`。

技术 owner：`TECH_01` 到 `TECH_10`，按 feature 行消费；`TECH_11` 在本版本 deferred。

工程执行：

- Release 概设：`docs/architecture/repository/RELEASE_FIN_IA_0_1_EXECUTION_PLAN_20260717.zh-CN.md`；
- 产品与工程详设：`docs/architecture/repository/RELEASE_FIN_IA_0_1_DETAILED_PRODUCT_TECHNICAL_DESIGN_20260717.zh-CN.md`；
- 机器执行清单：`configs/releases/fin_ia_0_1_detailed_execution_backlog_v1_0.json`。
