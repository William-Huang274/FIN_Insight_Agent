# REL-PROD-001：FIN 0.1 Internal Alpha 执行计划

日期：2026-07-17
状态：`release_scope_v1_2_accepted / fixture_shadow_internal_development_admitted / FIN_0_1_release_blocked_by_RG1_vertical_path`

## 1. Release Identity

```yaml
release_id: REL-PROD-001
version: FIN 0.1 Internal Alpha
release_contract_version: v1.2
release_channel: internal_alpha
target_product_maturity: L2_internal_dogfood_pass
anchor_case_target: R2_research_valid
production_readiness: not_admitted
legacy_authority_status: retained_until_separate_cutover
foundation_entry: REL-FND-001 POINT01_FOUNDATION_ALPHA_CONTRACT_RUNTIME_PROOF_COMPLETE
development_admission: fixture_shadow_internal_development_only
release_admission: P07.5 after RG1-RG5 only
timebox: one four-week product train
```

这是下一项真正的产品上线版本，但“上线”仅指内部 analyst/senior 可使用的受限版本。它不面向客户，不提供生产 SLA，不授权真实客户数据、商业数据采购、自动交易、broad full-chain 或 production cutover。完整功能范围由 `docs/product/FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX_20260717.zh-CN.md` 和 `configs/releases/fin_ia_0_1_release_contract_v1_1.json` 冻结；P36 六条产业链只定义 Anchor Case 校准覆盖，不定义产品全部功能。

本文是 Release 概设，只定义目标、范围、Point 顺序和 gate。页面、对象、API、状态、权限、代码目录、38 个 execution points、四阶段验收、测试和回滚的可执行详设，以 `RELEASE_FIN_IA_0_1_DETAILED_PRODUCT_TECHNICAL_DESIGN_20260717.zh-CN.md` 和 `configs/releases/fin_ia_0_1_detailed_execution_backlog_v1_1.json` 为准。任何 Point child plan 不得只引用本文后自行脑补实现。

## 2. 用户工作与结果

目标用户：内部投研 analyst 和 senior reviewer。

目标工作：在一个 ResearchCase 工作台中完成一次 AI infrastructure 深度研究，从任务创建、计划审核、执行观察、证据/数字检查、Workpaper、targeted repair、LeadReview、Writer no-source、human review 到 provenance 回溯形成完整闭环。研究内容需要回答 AI 基建需求如何沿 accelerator、server OEM、foundry/advanced packaging、HBM、semicap 转化为收入和利润，区分真实证据、proxy、margin dilution、瓶颈租、capex digestion、export control 和 price-in 风险。

用户可见结果：

- Dashboard / Task Center 和可创建、恢复的 ResearchCase；
- 可人工审阅的 Objective/Plan，以及由 Lead 动态编译的 10-20 个 DecisionSurface cells；
- Activity/Trace 中的 workstream、attempt、tool/model stage、typed stop、cancel 和 targeted resume；
- Evidence/Numeric Workbench 中每个 cell 的 accepted/context/rejected/gap、citation、row/unit/period/formula；
- 按判断组织的 Workpaper、counter-thesis、What-Would-Change 和 Repair Queue；
- LeadReview、WriterAdmission 和 Writer no-source 的内部 HTML/Markdown；
- cell/evidence/number/claim/artifact 级 human review 和 exact version；
- claim -> cell -> evidence -> tool/observation -> parser/numeric -> promotion 的双向 lineage；
- 当前 Case 内一次 bounded follow-up，能够解释判断、缺口和改变观点条件。

## 3. 产品功能与 Anchor DecisionSurface

### 3.1 Release Feature Groups

| Feature group | Feature IDs | 用户结果 | Primary delivery workstream |
| --- | --- | --- | --- |
| Product entry / control | `P001-F01`-`F04` | 创建 Case、审计划、看状态、暂停/恢复 | WS-A Research Control & Product |
| Evidence / numeric integrity | `P001-F05`-`F07` | 查到什么、为何能用、数字如何复算 | WS-B Research Integrity & Judgment |
| Workpaper / repair / Lead | `P001-F08`-`F10` | 形成判断底稿、按来源 repair、Writer 前主审 | WS-B Research Integrity & Judgment |
| Deliverable / review / trace | `P001-F11`-`F14` | 内部交付、exact-version review、双向追溯和当前 Case 追问 | WS-C Workbench & Quality |
| Eval / release feedback | `P001-F15` | 研究结果、使用价值、known gaps 和 rollback 可复核 | WS-C Workbench & Quality |

每个 Point 可以消费多个 TECH owner，但实现只能落入以上三个 delivery workstreams，避免按 TECH_01-10 建十条互不闭环的横向工程线。

### 3.2 Frontend Delivery Contract

FIN 0.1 包含前端工程建设。主线复用现有 `apps/workbench/frontend` 的 React 19 + TypeScript + Vite，以及 `apps/workbench/backend` 的 FastAPI；不新建第二套前端或平行 API source of truth。现有页面和 R53-R60 projection 可作为 adapter/参考，但不能直接宣称满足 FIN 0.1 的 canonical Case/DecisionSurface/Evidence/Review 合同。

前端代码应从当前单文件应用逐步拆成 `app shell + feature modules + typed API client + shared state/status components`。至少按以下 feature boundary 拆分：Task Center、Case Overview/Plan、DecisionSurface、Evidence/Numeric、Workpaper/Repair、Deliverable/Review、Activity/Trace。不得继续把 FIN 0.1 全部功能堆入现有 `main.tsx`。

前端必须消费版本化 product API，不直接读取 SQLite、runtime 文件目录或内部 Python object。SSE/polling 只负责 activity 更新；所有 mutation 必须携带 Case/artifact version、actor 和幂等 key，并呈现 stale/superseded/conflict 结果。

首版采用 desktop-first，1024px 以上可用；客户级视觉系统和移动端不是 gate。但 loading、empty、running、awaiting review、typed gap、failure/next action、stale、superseded、permission denied 必须有明确状态，不得只在 console/log 暴露。

### 3.3 Dynamic DecisionSurface Policy

Anchor 的 DecisionSurface 使用：

```text
Universal Cell Archetype
 + AI Infrastructure Sector Pack
 + bounded P36 case delta
 -> 10-20 runtime DecisionSurfaceCells（目标 12-16）
```

以下六项是必选 `cell families`，不是固定六个 runtime cells：

| Cell family | 必答机制 | 必需证据类型 |
| --- | --- | --- |
| Accelerator | demand、value capture、客户/平台集中和出口/price-in | 财务 exact rows、产品/部署、客户/供应链、市场边界 |
| Server OEM | 订单/收入真实性、毛利、cash conversion 和商业模式差异 | segment/业务线、订单/部署、毛利/营运资本、同行差异 |
| Foundry / Advanced Packaging | 产能、利用率、capex、瓶颈和瓶颈租持续性 | 官方产能/扩产、资本开支、供需、客户/供应链 |
| HBM | demand、供给、定价、利润捕获、客户集中和供给释放 | 产品代际、产能/供给、财务/毛利、客户/替代 |
| Semicap | capex read-through、滞后性、周期和出口政策 | 订单/收入/segment、foundry/memory capex、周期/政策 |
| Cross-chain Counterevidence / WWC | capex digestion、供给释放、出口管制、估值和需求下修 | 反方、阈值、当前值、attempted evidence 和 gap |

每个实际 cell 至少包含：`cell_conclusion`、`evidence_quality_grade`、`real_demand_vs_proxy`、`numeric_sanity_status`、`counterevidence`、`gap_status` 和 `what_would_change`。Planning checkpoint 允许 reviewer 裁剪、拆分和增加 cells，但不得静默删除 risk/counterevidence、material numeric sanity 或 writer boundary。

## 4. Case Set

- Anchor：P36 AI Infrastructure，完整执行到内部 memo/Workbench；
- Regression A：Enterprise AI / SaaS，只验证 DecisionSurface 泛化、slot/owner 和 Writer boundary；
- Regression B：US Banks，只验证 sector-specific cells、period/metric policy 和 missing/commercial gap；
- WorkBuddy 输出只作为 defect/pattern candidate，不继承其事实、数字、估值、排名、概率或 source strategy。

## 5. Point / Workstream 路线

Point 02-07 的正式 child plan 需要按 Point 模板冻结；本 release 先固定其消费关系和顺序：

前端不是 Point 06 的末端包装，而是跨 Point 的纵向交付轨：

| Point | 前端增量 | 最小可操作验收 |
| --- | --- | --- |
| Point 02 | App shell、Task Center、Case Overview/Plan、DecisionSurface、Activity skeleton | 用户不编辑 JSON 即可建 Case、审计划、启动/取消任务并看到状态 |
| Point 03 | Evidence Search Activity、Evidence Workbench | 可按 cell 查看、筛选、展开来源并 reject/request repair |
| Point 04 | Numeric Drawer、Fact Table、formula/lineage view | 可定位 entity/period/unit/scale/row/formula 和复算结果 |
| Point 05 | Workpaper、Repair Queue、LeadReview、same-Case follow-up | 可审判断、派 repair、执行 writer admission 和一次追问 |
| Point 06 | Deliverable、Comments/Review Queue、Trace Explorer | 可在 exact version 上 comment/return/accept，并双向追溯 material claim |
| Point 07 | E2E、可访问性、性能与 dogfood 修复 | analyst/senior 可连续完成 RG1 工作流，无隐藏 JSON 操作 |

前端技术工作由 WS-A 负责 App shell、Case/control/plan/activity；WS-C 负责 Workbench、deliverable/review/trace 和 product E2E；WS-B 提供 Evidence/Numeric/Workpaper 的 typed projections 与 action contracts。前端是消费方，不复制 Evidence Gate、Numeric Gate 或 review authority。

### R1 / Point 02：Case + DecisionSurface Runtime Entry

- 消费 Point 01 canonical control/DecisionSurface objects；
- 实现 `P001-F01`-`F04`：Dashboard/Task Center、ResearchCase workspace、Objective/Plan、DecisionSurface、Activity timeline 的前端 route、typed API client 和最小交互；
- 让真实 P36 task 通过 archetype + sector pack + case delta 编译 10-20 个 cells 和 EvidenceSlots；
- 提供 planning checkpoint，reviewer 可以在执行前修改/退回 cells、source policy 和 stop rules；
- Lead 只 planning，不检索、不补源、不写最终结论；
- 输出 immutable DecisionSurfaceContract 和 WorkUnits。

Exit：用户无需编辑 JSON 即可创建/打开 Case、审阅计划并启动/取消任务；route refresh 可恢复 Case/version；10-20 个 cell/owner/slot/stop rule 完整；六个 mandatory families 有覆盖；SaaS/Bank regression 无 material generic-dimension collapse。

### R2 / Point 03：Evidence Addressing / Retrieval / Repair

- 实现 `P001-F05`-`F06` 的 Evidence Search Activity 与 Evidence Workbench；
- 前端按 cell/source/status/filter 展示候选与 promotion，并提供 reject/request repair action；
- EvidenceRequest 驱动 internal RAG、SQL、graph 和受限 SourceHunter；
- metadata-first filter、top-K/rerank、neighbor/section/table expansion；
- 区分 retrieval exhausted、parser gap、commercial gap 和 source needed；
- supervisor supplement 只进入 supplement ledger，必须经 SourceHunter/Evidence Gate 才可 runtime 化。

Exit：每个 cell 有 CandidateBundle、RejectedCandidateLedger 或 typed gap；用户能在 surface 查看 source/citation/authority/promotion；至少一条 neighbor/table repair 被真实消费。

### R3 / Point 04：Parser / Numeric / Evidence Promotion

- 实现 `P001-F07` Numeric Drawer / Fact Table；
- 前端展示 table/row/unit/period/scale、公式、inputs/result 和 ambiguity，不把原始 JSON 作为主要视图；
- exact row selector、entity/period/unit/scale/table lineage；
- material growth/margin/bridge/multiple 使用 NumericProgramTrace；
- deterministic hard gate + evidence-agent semantic suggestion；
- false promotion negative controls。

Exit：全部 material numeric claims 可复算且用户可查看 input/formula/result；零已知 false accepted evidence；parser failure 不冒充 source absent。

### R4 / Point 05：Domain Judgment / Counterevidence / Lead Repair

- 实现 `P001-F08`-`F10` 和 `F14`：Workpaper、Repair Queue、LeadReview/WriterAdmission、bounded same-Case explanation；
- 前端提供 judgment/counterevidence/WWC 阅读、RepairTicket action、Lead decision 和 follow-up thread；
- Product/Industry、Fundamental、Market/Capital、Risk operators 投影到动态 cells；
- 输出 DomainCellJudgmentPack；
- Lead 执行 cross-cell conflict/coverage/story review；
- repair 路由回来源 owner，Lead 不成为万能补源 agent；
- What-Would-Change 独立展示推理摘要、尝试证据和未解决缺口。

Exit：全部 required cells 均为 accepted/typed gap/commercial gap/human review；至少一条真实 repair loop 关闭或 attempt-backed stop；Workpaper 不由 evidence dump 或 specialist prose 直接拼装；一次当前 Case follow-up 保持 as-of/source boundary。

### R5 / Point 06：Writer / Workbench / Provenance

- 实现 `P001-F11`-`F13` 的 Deliverable、Human Review 和 Trace Explorer；
- Writer 只消费冻结 DecisionSurfacePack、WriterBrief、approved refs 和 typed gaps；
- 输出内部 HTML/Markdown，不要求首版 PPT/Excel；
- Workbench 提供可操作 UI，显示 matrix、candidate/promotion、numeric trace、repair、review action；JSON/API 只作为 replay/debug surface；
- Point 06 负责整合而非首次开始前端：补齐 Deliverable/Review/Trace，统一此前 Point 02-05 已交付 surfaces 的导航、状态和 action semantics；
- material claim provenance 贯通。

Exit：Writer tool/source call=0；全部 material claims 有 lineage 或明确 gap；HTML/Markdown 语义一致；一个 exact artifact version 可 comment/return/request repair/accept。

### R6 / Point 07：Dogfood / Eval / Release

- 实现 `P001-F15` Quality / Release Summary，不新增新的主产品功能；
- P36 Anchor 完整内部 dogfood；
- SaaS/Bank 运行结构回归；
- reviewer 记录 accept/conditional/reject 和 edit reasons；
- 记录 time-to-workpaper、review burden、tool/model cost 和 analyst repeated-work baseline；
- 执行 RG1-RG5、rollback 和 release note。

Exit：达到本计划第 8 节全部 hard gates，发布 `FIN 0.1 Internal Alpha`。

### 5.1 Point 归属与版本列车执行顺序

Point 02-07 继续定义能力 owner、最终 Point closeout 和 release traceability，但不得再按 Point 编号形成“先完整做完 Point 02，再完整做完 Point 03”的瀑布。实际建设顺序由 `configs/releases/fin_ia_0_1_vertical_release_train_overlay_v1_0.json` 控制，并遵守以下规则：

1. 每周先冻结一个用户可见纵向结果，再反推该周需要消费的 execution points 和 maturity；
2. downstream 可以消费 upstream 的 exact、versioned、tranche-scoped artifact，不要求 upstream 已完成整个 Point closeout；
3. upstream Point 的最终 `full/calibrated` 依赖仍按 backlog 保留，tranche 消费不得写成 Point complete；
4. `skeleton/fixture/full/calibrated` 是证据成熟度，不是每个 EP 都必须等待前一阶段独立审批后才能进入下一项工作的四道流水 gate；
5. 每个周末必须运行一条跨 owner 的 integration probe，验证真实产品 entry、application service、store/projection、下游 consumer 和 UI，而不是只验证 schema 常量；
6. reviewer 只能用既有 acceptance、RG1-RG5 或安全底线阻断当前 tranche；未被当前路径消费的 hardening 默认进入 deferred backlog；
7. 版本列车不新增 gate family。integration probe 是早期缺陷发现机制，不是新的 release authority。

这项裁决不改变 `P001-F01`-`F15`、Point owner、ReleaseContract v1.2 或最终 RG1-RG5，只纠正建设和验证顺序。

## 6. 四周日程

| 周次 | 必须完成 | 不在本周扩大 |
| --- | --- | --- |
| W1 | `F01-F06`：产品入口、动态计划、activity、Evidence Workbench；选 3 个代表 cells 打通最薄纵向链 | 新行业、客户级视觉、多格式 |
| W2 | `F07-F10/F14`：Numeric、Workpaper、repair、LeadReview；Anchor 10-20 cells 全部达到终态 | monitoring、quant、企业 admin |
| W3 | `F11-F13`：HTML/Markdown、Human Review、Trace；P36 dogfood 和两 regression cases | 第二 Anchor、全部 source provider |
| W4 | R6、review、rollback、release freeze | 新功能和非阻断重构 |

若 W2 结束纵向链仍未到 DomainCellJudgmentPack，应减小非 material EvidenceSlots、provider breadth 或 presentation polish，而不是删除产品入口/Workbench/Workpaper/Review 闭环、六个必选 families 或 Evidence/Numeric gate。

具体每个 EP 在各周要求达到的 maturity、tranche-scoped dependency、integration probe、阻断条件和 deferred 项，以 vertical release train overlay 为准。overlay 与 backlog 冲突时必须停止并修订合同，不能由执行者静默选择。

## 7. Test Profiles

### Fast

- schema/serialization；
- cell/slot/owner/stop rules；
- feature-to-surface route 和 UI state projection；
- frontend typecheck/build、API contract types、route/state reducer；
- writer no-source；
- unit/period/scale/numeric trace；
- promotion hard-fail；
- legacy/canonical no-dual-write。

### Component

- Task Center -> ResearchCase -> planning checkpoint；
- DecisionSurface -> EvidenceRequest；
- retrieval -> neighbor/table expansion；
- parser/numeric -> Evidence Gate；
- DomainCellJudgment -> LeadReview -> WriterAdmission；
- Workbench projection/provenance；
- ReviewAction -> RepairTicket / ArtifactVersion。
- 每个 surface 的 loading/empty/error/stale/superseded/action component test。

### Operational

- bounded internal RAG/SQL/tool invocation；
- one repair/resume；
- one same-Case explanation follow-up；
- one rollback；
- provider/model node runs only after explicit budget/permission preflight。

### Release

- P36 complete Anchor Case；
- SaaS/Bank structural regressions；
- Task Center/Case workspace/Workbench/Review product E2E；
- 浏览器 E2E 覆盖 create -> plan -> run -> inspect -> repair -> admit -> review -> trace -> follow-up；
- 1024px 和 1440px 无关键控件遮挡，键盘可完成主要 review action；
- exact artifact review；
- RG1-RG5；
- known-gap and rollback manifest。

## 8. Release Gates

| Gate | Hard acceptance |
| --- | --- |
| `RG1_vertical_path` | 用户从 Task Center 创建 Case，经 planning checkpoint、execution、Workbench、Workpaper、LeadReview、HTML/Markdown、Human Review 完成闭环；10-20 required cells 有终态；核心路径可 rollback；并必须验证 exact package 从 entry→adapter→subprocess→clean-child 的 identity 不漂移，完成一次 bounded operational vertical run，持久化 actual/oracle/reviewer/Workbench 结果 |
| `RG2_evidence_numeric_integrity` | 0 known false promotions；100% material numeric claims 有 trace；Writer source/tool calls=0；supplement boundary 100% 正确 |
| `RG3_research_outcome` | Anchor 达到 R2；六个 mandatory families 和 dynamic required cells、counterevidence、gap、LeadReview 无 hard omission；SaaS/Bank 结构回归通过 |
| `RG4_review_product_value` | senior 能在产品 surface 定位每个 material claim 来源和修改点；至少一轮真实 review 与一次 bounded follow-up 被记录；time-to-workpaper/review burden/repeated-work/tool-model cost 建立 baseline |
| `RG5_release_rollback` | exact candidate/artifact hashes、known gaps、deferred backlog、rollback 和 release note 完整 |

R3 reviewer acceptance 是首版 stretch outcome，不作为 FIN 0.1 的强制发布条件；但必须有 reviewer 可审和反馈记录。

## 9. Hard Blockers

- false accepted evidence；
- material numeric corruption 或不可复算；
- Writer/Presentation 私自补源；
- supervisor supplement 被标记为 runtime evidence；
- material provenance 缺失；
- canonical/legacy 双 authoritative write；
- 纵向链不可运行且无 typed stop/rollback；
- secret、权限或真实数据破坏。

同一 blocker 最多两轮 bounded repair；之后按 Release Operating Model 做 block/defer/stop 裁决。

## 10. Deferred To Later Releases

- Data Room/private/licensed data 和 OCR 全链；
- Watchlist/Monitoring 和 R4 longitudinal refresh；
- Research-to-Quant、backtest 和 paper trading；
- 全行业 Sector Packs；
- PPT/Excel/PDF/dashboard 全格式一致性；
- SSO/SCIM/KMS/DLP/enterprise tenant operations；
- 完整 valuation/forecast/scenario engine；
- 完整 consensus/fund flow/options/CDS；
- production cutover、正式客户 SLA 和多租户上线。

## 11. Entry Checklist

以下开发准入项满足后才进入 W1；RG1 operational debt 继续作为 P07.5 前 release blocker 跟踪，不反向阻塞 fixture/shadow/internal development：

- [x] Point 01 narrow scope closeout 写入 `POINT01_FOUNDATION_ALPHA_CONTRACT_RUNTIME_PROOF_COMPLETE`；
- [ ] release blocker tracking：`RG1_vertical_path` 仍须在 P07.5 前补齐 entry-to-clean-child identity、bounded operational vertical run 与 actual/oracle/reviewer/Workbench 结果；
- [x] Point 01 `production_readiness=not_admitted`；
- [x] legacy global authority retained；
- [x] ReleaseContract v1.2、detailed backlog v1.1 与 FeatureScopeMatrix JSON digest 冻结；
- [ ] `P02.0` 既有 owner、`/api/v1`、route/state/error、rollback ADR、依赖设计 lock 与 cross-owner artifacts 完成一次 VT0 bounded set-closure repair 并通过独立复核；
- [ ] 八个 required Point 02 browser surfaces 的 route action、canonical command/read model、OpenAPI operation/schema 和 owner set 逐项闭合；
- [x] P36 Anchor、SaaS、Bank fixture/profile requirements 冻结（仅 static/fixture/fast/component）；
- [ ] Point 02 child plan 的 historical candidate evidence 经 VT0 修复后重新签发当前有效的 P02.0 closeout；
- [ ] `P001-F01`-`F15` 的 product/engineering acceptance 仍需后续 Point 02-07 implementation evidence；
- [ ] model/tool/network/paid budget 单独批准或保持 disabled。

VT0 修复后的 `P02.0` closeout 只使 `P02.1`、`P02.2` 进入 `ready_for_skeleton_fixture_internal_development_only`，不授予 runtime、operational、browser、release 或 RG1 bypass admission。

## 12. Closeout 输出

版本完成时必须交付：

- `ReleaseEvidenceManifest`；
- 可操作的 Dashboard/Task Center 和 ResearchCase Workspace；
- FIN 0.1 React/Vite 前端 build、七个 product routes/surfaces、typed API client 和浏览器 E2E evidence；
- P36 DecisionSurfacePack、WriterBrief、HTML/Markdown、Workbench projection；
- material claim/numeric/provenance audit；
- reviewer action 和 known-gap ledger；
- one repair/resume 和 one bounded follow-up evidence；
- time-to-workpaper、review burden、repeated-work、tool/model usage baseline；
- RG1-RG5 结果；
- rollback result；
- FIN 0.1 release note；
- capability maturity delta 和 FIN 0.2 Earnings Alpha handoff。
