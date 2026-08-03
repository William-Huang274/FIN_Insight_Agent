# FinSight PRD 全量吸收与版本分配矩阵

日期：2026-07-19
状态：`accepted_product_release_allocation / progress_owned_by_program_backlog`
进度权威：无；本文只拥有 PRD 功能到版本的分配，不拥有实施状态

## 1. 目的

本文防止 FIN 0.1 的 Agent 主线建设遮蔽 PRD 中的数据、底稿、交付、记忆、监控、量化和企业治理能力。它完整吸收 PRD 的五个产品平面、13 个功能模块、B0-B7 和 F01-F15，并为每项标记：

- `FIN_0_1`：当前窄而完整的发布范围；
- `FIN_0_2`：Earnings Review Alpha；
- `FIN_0_3`：Review & Memory Beta；
- `FIN_0_4`：Cross-sector Beta；
- `FIN_0_5`：Enterprise Pilot；
- `post_FIN_0_3_unscheduled`：已有依赖顺序但尚未冻结 Release ID；
- `assisted_experimental_track`：实验线，不阻塞早期主发布；
- `non_goal`：PRD 明确不做。

实时进度仍只能由 `configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json` 拥有。本文不是第二份 backlog。

### 1.1 FIN 0.1 内部 patch-line 澄清（2026-07-31）

第一轮 S0–S5 形成的诚实阻断工程基线编号为 `FIN 0.1.1`；共同 Runtime、contract compiler、proof hermeticity 和三案例 transfer qualification 在不改变 FIN 0.1 产品范围的前提下进入 `FIN 0.1.2`。

这两个编号是 FIN 0.1 内部工程迭代，不新增 PRD 产品 Slice。原分配保持不变：

- `FIN 0.2` 仍为 `Earnings Review Alpha`；
- B1、Earnings Task/Workpaper/Report、精确财务/segment/guidance 仍由 FIN 0.2 拥有；
- FIN 0.1 未完成的通用 Runtime 与 transfer 承诺不能改写成 FIN 0.2 的新定义。

版本谱系权威说明见 `docs/product/FIN_0_1_1_0_1_2_VERSION_LINEAGE_AND_RELEASE_CADENCE_DECISION_20260731.zh-CN.md`。

### 1.2 FIN 0.1.1 / 0.1.2 能力验收纠偏（2026-08-04）

RAG、Agentic Search 和 Agentic Research 不是统一分配到 FIN 0.2 的能力。`F05`、public/local Evidence、三-cell judgment、targeted repair、Lead/Writer、Human Review 和 Trace 继续属于 FIN 0.1 bounded release scope。FIN 0.1.1 做过本地受控检索与历史 Agent 运行，但没有取得三案例/current-runtime/product-accepted 证明；FIN 0.1.2 当前 S3 又明确使用 frozen evidence、关闭 source network/external tools，因此 S3 success 不能隐含 F05 pass。

尚未开始的 S4/S5 已据此重排：S4 独立承担自然 Case、真实 public/local Agentic Search、Evidence Gate、Agentic Research、三案例 transfer、Workbench 和 Human Review；S5 按 F01–F15 与 RG1–RG5 签发。完整对账见 `docs/product/FIN_0_1_1_0_1_2_PRD_CAPABILITY_ALIGNMENT_AND_S0_TO_S5_REBASELINE_20260804.zh-CN.md`。FIN 0.2 仍为 Earnings Review Alpha。

## 2. 五个产品平面

| PRD 产品平面 | 长期产品结果 | FIN 0.1 吸收 | 后续明确归属 |
| --- | --- | --- | --- |
| Research Control Plane | ResearchCase 的范围、责任、状态、LeadReview、Gap/Repair 和下一步可控 | Case/Objective、三-cell DecisionSurface、bounded Run、LeadReview、Repair Queue | FIN 0.2 增加 Earnings 模式；FIN 0.3 增加 correction/refresh/supersession；FIN 0.5 增加企业 workflow |
| Evidence & Modeling Plane | Evidence、Data Room、RAG/DB/Web/Graph、Numeric/Valuation/Scenario 可验证可复算 | public/local bounded search、Evidence Workbench、Numeric、bounded Graph view、三-cell judgment | FIN 0.2 精确财务/segment/guidance；FIN 0.4 跨行业；FIN 0.5 私有 Data Room；Quant 走实验线 |
| Institutional Memory Plane | accepted/rejected evidence、judgment、review decision、Case history 和 method 可寻址、可失效 | exact Case/Run/Artifact history、role context、MemoryWriteCandidate 与 registry lifecycle 边界 | FIN 0.3 完成 correction reuse、follow-up、selective refresh 和 bounded R4 |
| Review & Delivery Plane | Workpaper、Review、ArtifactConsistency、Deliverable、Approval/Release | Workpaper、HTML/Markdown Report、layered Verifier、exact Human Review、Trace | FIN 0.3 强化 exact-version 修订复用；全格式交付在主线稳定后单独排期；FIN 0.5 企业审批/审计 |
| Monitoring & Learning Plane | Watchlist、WWC、staleness、refresh、Eval 和 governed improvement | active WWC、hard/research/product eval、known gaps、release feedback | FIN 0.3 selective refresh；Watchlist/Monitoring 在 FIN 0.3 后独立版本；生产学习治理后置 |

## 3. 十三个功能模块

| PRD 功能模块 | FIN 0.1 承诺 | 后续版本分配 | 当前版本不应冒充 |
| --- | --- | --- | --- |
| 6.1 Dashboard / Home | Task/Case、状态、失败、待审、成本/调用摘要、next action | FIN 0.3 增加 stale/refresh；Monitoring 版本增加事件/watchlist | 完整组合覆盖、实时事件中心、团队生产 dashboard |
| 6.2 Research Task Center | 发起 P36 deep-research Case，保存 Objective/as-of/source/reviewer/budget | FIN 0.2 Earnings 模板；FIN 0.4 行业模板；FIN 0.5 企业项目空间 | PRD 列出的所有任务模式均已可用 |
| 6.3 Input / Data Room | 不进入 FIN 0.1 release；只消费仓库已准入资料 | FIN 0.5：上传、解析、OCR、table/cell、permission、private evidence | 用户上传或私有/licensed data 已接入 |
| 6.4 Evidence Workbench | 三 Case 的 candidate/accepted/context/rejected/gap、authority、citation、repair | FIN 0.5 增加 private Data Room evidence | 全来源、全许可、生产 Evidence coverage |
| 6.5 Workpaper Builder | 三 cells 的 Evidence/Numeric/Judgment/counterevidence/WWC/gap 和 review trail | FIN 0.2 Earnings workpaper；FIN 0.4 sector packs；FIN 0.3 revision reuse | 完整估值、所有 PRD 维度或全行业底稿 |
| 6.6 Graph / Visualization Workspace | bounded value-chain/claim/evidence graph drilldown，显示 edge type/ref/authority/boundary | FIN 0.4 扩跨行业 ontology；Monitoring 版本增加 timeline/risk map | 完整图谱工作室、资本/持仓/风险全图 |
| 6.7 Research-to-Quant Lab | 不进入 FIN 0.1-FIN 0.5 主发布关键路径 | `assisted_experimental_track`：thesis-to-factor、PIT dataset、backtest、risk、paper trading | 真实资金、投资建议、无人工批准自动升级 |
| 6.8 Deliverable Studio | internal HTML/Markdown、表格/引用、版本、手工编辑入口 | FIN 0.2 Earnings template；FIN 0.3 revision consistency；全格式交付单独排期 | Word/PPT/Excel/PDF 已全格式一致 |
| 6.9 Watchlist / Monitoring | FIN 0.1 只有 WWC 和 known gaps，不运行持续监控 | `post_FIN_0_3_unscheduled`：watchlist、event trigger、staleness、scheduled review | 自动刷新、实时信号或持续覆盖已经上线 |
| 6.10 Human Review / Approval | exact Case/Cell/Claim/Evidence/Numeric/Artifact comment/return/repair/accept | FIN 0.3 correction reuse/conditional/supersede；FIN 0.5 企业 approval integration | OA/SSO/合规签字或客户 release 已完成 |
| 6.11 Admin / Governance | Profile、Agent/Skill/Tool/Graph version、权限/预算摘要、Trace、rollback | FIN 0.5 RBAC/private isolation/audit/config rollout；production 再做 SSO/SCIM/KMS/DLP/SLO | 企业生产治理已经具备 |
| 6.12 Institutional Memory / Case History | exact Run history、reconstructable context、stale/revoked memory 不得提权 | FIN 0.3 reviewer correction reuse、Case follow-up、selective refresh、bounded R4 | 跨季度长期记忆和自动事实复用已完成 |
| 6.13 Human-AI Accountability | actor/profile/Agent/Skill/Tool/event/artifact/review exact attribution | FIN 0.3 扩 revision/refresh；FIN 0.5 扩 enterprise audit/export | 法律责任自动裁定或 AI 使用量员工绩效化 |

## 4. B0-B7 产品切片

| PRD Slice | 版本分配 | 当前解释 |
| --- | --- | --- |
| B0 产品壳与任务闭环 | FIN 0.1 | Case、Task Center、状态、Evidence、Workpaper、Report、Trace 的窄完整闭环 |
| B1 财报/业绩点评 | FIN 0.2 | 精确三表、segment、guidance、同比环比、市场反应和反方 |
| B2 公司深度初稿 | FIN 0.1 bounded；FIN 0.4 扩展 | 当前只覆盖 P36 三-cell、三-Case，不宣称完整公司深度所有维度 |
| B3 产品/竞品/供应链研究 | FIN 0.1 bounded；FIN 0.4 扩展 | 当前交付 bounded Graph view 和 P36 价值链证据，不宣称通用全行业图谱 |
| B4 Data Room / 文件上传 | FIN 0.5 | 与 private evidence、RBAC、permission、audit 一起进入 Enterprise Pilot |
| B5 Watchlist / Monitoring | FIN 0.3 后独立排期 | 依赖稳定 Case、Memory、staleness 和 selective refresh |
| B6 Research-to-Quant Lab | assisted experimental track | 与主产品共享 thesis/evidence lineage，但不阻塞 FIN 0.1-FIN 0.5 |
| B7 DecisionSurface / Evidence Repair | FIN 0.1 | 三-cell plan、EvidenceRequest、NumericTrace、Repair、DecisionSurfacePack 和 Workbench |

## 5. F01-F15 Release Feature

| Feature | FIN 0.1 状态 | 后续延伸 |
| --- | --- | --- |
| F01 Dashboard / Task Center | `release_critical_bounded` | FIN 0.3 stale/refresh；Monitoring 事件入口 |
| F02 ResearchCase / Objective | `release_critical_bounded` | FIN 0.2 Earnings Objective；FIN 0.3 lifecycle |
| F03 Dynamic DecisionSurface | `release_critical_three_active_cells` | FIN 0.2 Earnings cells；FIN 0.4 cross-sector；10-20 active cells 后置 |
| F04 Durable execution | `release_critical_bounded_run_cancel_stop_resume` | FIN 0.3 refresh/rebase；production scheduler 后置 |
| F05 Agentic Search | `release_critical_public_local_bounded` | FIN 0.5 private sources；商业源另行授权 |
| F06 Evidence Workbench | `release_critical_three_case` | FIN 0.5 private/licensed evidence |
| F07 Numeric / Fact audit | `release_critical_three_case` | FIN 0.2 exact Earnings；FIN 0.4 sector numeric packs |
| F08 Workpaper / Domain Judgment | `release_critical_three_cell` | FIN 0.2 Earnings；FIN 0.4 cross-sector |
| F09 Gap / Repair Queue | `release_critical_targeted` | FIN 0.3 repair history reuse |
| F10 Lead Review / Writer Admission | `release_critical` | FIN 0.3 revision/reapproval |
| F11 Internal Deliverable | `release_critical_HTML_Markdown` | multi-format consistency 后续独立排期 |
| F12 Human Review / Accountability | `release_critical_exact_internal` | FIN 0.3 full review lifecycle；FIN 0.5 enterprise approval |
| F13 Provenance / Trace | `release_critical_material_claims` | FIN 0.5 private/audit export |
| F14 Same-Case explanation | `demo_support_nonblocking_exact_why_gap_WWC` | FIN 0.3 升为 release-critical follow-up/memory |
| F15 Quality / Release Feedback | `release_critical` | FIN 0.3 refresh quality；FIN 0.5 enterprise operational quality |

## 6. 具名 Roadmap

| Roadmap ID | 目标版本/轨道 | 吸收内容 | 进入条件 |
| --- | --- | --- | --- |
| `RM-002-EARNINGS` | REL-PROD-002 / FIN 0.2 | B1、Earnings Task/Workpaper/Report、财务/segment/guidance | FIN 0.1 Runtime 和 exact artifact 主线稳定 |
| `RM-003-REVIEW-MEMORY` | REL-PROD-003 / FIN 0.3 | Institutional Memory、correction reuse、follow-up、selective refresh、bounded R4 | exact Review 和 supersession 可靠 |
| `RM-004-CROSS-SECTOR` | REL-PROD-004 / FIN 0.4 | SaaS、银行、消费/工业 Sector Pack，Graph/Numeric/Judgment 泛化 | FIN 0.1/0.2 方法与 Case policy 可迁移 |
| `RM-005-DATAROOM-ENTERPRISE` | REL-PROD-005 / FIN 0.5 | B4、private evidence、RBAC、audit、cross-artifact consistency | public/internal workflow 与权限主账本稳定 |
| `RM-MONITORING` | post FIN 0.3，Release ID 未冻结 | B5 Watchlist、event trigger、staleness、scheduled refresh | FIN 0.3 Case/Memory/selective refresh 完成 |
| `RM-QUANT` | assisted experimental track | B6 thesis-to-factor、PIT dataset、backtest、risk、paper trading | 独立 Human approval；不阻塞主发布 |
| `RM-MULTIFORMAT` | post FIN 0.3，Release ID 未冻结 | Word/PPT/Excel/PDF 和 ArtifactConsistency | HTML/Markdown exact model 稳定 |
| `RM-ENTERPRISE-PRODUCTION` | enterprise pilot 后独立准入 | SSO/SCIM/KMS/DLP/SLA/HA/DR、production cutover | FIN 0.5 和独立安全运维准入 |
| `RM-OPEN-COMPOSITION` | post FIN 0.1，Release ID 未冻结 | 用户可选 model/provider、approved Skill/Tool/Graph profile；高级 graph builder 后置 | D12 Profile 和配置发布治理稳定 |

## 7. 永久非目标

以下能力不进入上述 release ladder：自动确定买卖建议、替代投委会/合规/审计责任人、真实资金自动交易、高频执行、无人工批准的回测或 paper-trading promotion、无人工审阅的客户报告、弱社媒信号直接形成核心结论、用 AI 使用量评价员工、自动裁定法律责任、自建全球通用网页索引/foundation model，以及绕过 Evidence/Numeric/Review/Release 主账本的 provider 替换。

## 8. 与当前合同的待处理差异

用户接受 Program Plan 时必须同步升版 ReleaseContract 和 FeatureScope，不能静默覆盖：

1. 旧 FeatureScope 要求 10-20 active cells；D13 将 FIN 0.1 release depth 收窄为三个 active Agent cells，现有 10-cell deterministic preview 保留为非 Agent reference；
2. 旧 FeatureScope 将 F14 作为 required feature；D13 将它收窄为 exact why/gap/WWC 的非阻断辅助面，完整 follow-up 进入 FIN 0.3；
3. PRD B3 要求 ProductIntelligenceGraph 用户可见；Program Plan 必须在 S3 加入 bounded Graph drilldown，不能只记录后台 Graph 调用；
4. 三个 release Case 是 NVDA anchor、DELL/MU transfer proof；SaaS/Bank 仍只做结构泄漏回归。

这些产品范围重基线由 `fin_ia_0_1_feature_scope_matrix_v1_1.json` 和 `fin_ia_0_1_release_contract_v1_3.json` 承接。它们只准入 S1 fixture/shadow 实施，不授权模型、网络、真实业务 Case、release candidate 或 production。
