# FinSight 产品发布阶梯与版本节奏

日期：2026-07-17
状态：`accepted_product_operating_model / not_runtime_proof`

## 1. 目的

本文把 PRD 中的产品切片、L0-L4 产品成熟度和 R1-R4 ResearchCase 结果成熟度转换成稳定发布节奏。它回答“何时形成一个可用版本、版本面向谁、解决什么工作、允许带着哪些已知缺口发布”。技术执行、Point 模板和 gate 规则见 `docs/architecture/repository/RELEASE_OPERATING_MODEL_20260717.zh-CN.md`。

产品发布不再以“完成一个 TECH 文档”或“完成一个 Point milestone”为单位，而以一个用户可使用、可审阅、可回滚的纵向研究结果切片为单位。

## 2. 发布通道

| 通道 | 目标用户 | 最低产品级别 | 最低 Case 结果 | 可对外范围 |
| --- | --- | --- | --- | --- |
| `dev_snapshot` | 开发与自动化 | L0/L1 | 不要求 R1 | 不对外，不称为产品版本 |
| `foundation_alpha` | 平台开发者与内部 reviewer | L1 | 不要求 R2 | 只证明基础合同和迁移边界 |
| `internal_alpha` | 内部 analyst / senior reviewer | L2 | Anchor Case R2 | 仅内部使用，必须披露已知边界 |
| `calibration_beta` | 邀请制内部团队或设计合作方 | L2，向 L3 收敛 | 多 Case R2，至少一个 R3 | 非生产、受控数据和反馈范围 |
| `enterprise_pilot` | 指定试点机构 | L3 | 目标工作流稳定 R3 | 受控试点，独立安全和运维准入 |
| `production` | 正式企业客户 | L4 | 目标工作流稳定 R3，纵向能力按需 R4 | 正式合同、SLA、合规和生产责任 |

四个状态轴必须分别记录：

1. `release_channel`：本版本可以给谁使用；
2. `capability_maturity`：单项能力实现到 documented / fixture / runtime / dogfood 的哪一步；
3. `case_outcome`：每个 Case 达到 R1-R4 中哪一级；
4. `production_readiness`：是否获得真实企业部署准入。

任何一轴通过都不能替代其他轴。例如 Point 01 可以作为 `foundation_alpha` 关闭，同时保持 `production_readiness=not_admitted`；一个 P36 报告达到 R3，也不能证明整套产品达到 L4。

## 3. 四周产品列车

主产品采用四周固定列车：

| 周次 | 目标 | 冻结规则 |
| --- | --- | --- |
| 第 1 周 | 纵向链先跑通：输入到 Workbench/Artifact | 只实现本版本必需对象和 adapter |
| 第 2 周 | 补 Evidence、Numeric、Judgment 和产品 surface 质量 | 不扩展第二个主要用户工作流 |
| 第 3 周 | Anchor Case dogfood + 两个 regression cases | 只修 hard blocker 和高价值根因 |
| 第 4 周 | Reviewer、回滚、已知限制、版本冻结与发布 | 停止新增功能；不因非阻断改进延迟发布 |

辅助节奏：

- 每次合并运行 fast profile；
- 每周运行 component integration 和固定回归；
- enterprise pilot 前独立运行 operational/release/security qualification；
- 每季度复审 ICP、行业覆盖、数据授权、外部平台替代压力和企业 readiness。

## 4. 单版本范围上限

每个产品版本默认只允许：

- 一个主要用户工作流；
- 一个完整 Anchor Case；
- 两个结构或边界 regression cases；
- 最多三个 primary delivery workstreams；每个 workstream 可以消费多个 TECH owner 的稳定合同，但不得因此重建平行 source of truth；
- 最多一个 canonical authority cutover；
- 一个明确的用户可见结果；
- 一条经过验证的 rollback path。

若超出上限，必须拆分版本或记录书面 scope exception，不能通过延长同一版本无限吸收新问题。

## 5. 投入比例

未来三个主产品版本按以下基准分配：

- 50%：用户可见纵向功能；
- 20%：Evidence、数据、Parser、Numeric；
- 15%：Control/Harness/权限基础；
- 10%：Eval、dogfood、Reviewer；
- 5%：清理、文档、归档。

Control/Harness 可以超过 15%，但必须满足至少一项：修复当前版本已复现 hard blocker；是下一纵向切片的必需依赖；涉及数据破坏、权限、Evidence promotion 或 material number 正确性。仅因理论上还能增加防御层，不得占用当前产品列车。

## 6. 产品版本路线

| Release ID | 版本 | 主要工作 | 目标 |
| --- | --- | --- | --- |
| `REL-FND-001` | Foundation 0.1 | Point 01 Control + DecisionSurface foundation | 平台 L1；不是研究产品上线 |
| `REL-PROD-001` | FIN 0.1 Internal Alpha | B0 产品壳 + B2 深度底稿 + B3 bounded 产品/供应链 + B7 Evidence/Numeric/Repair 的 AI infra 纵向研究工作台 | 产品 L2；Anchor R2 |
| `REL-PROD-002` | FIN 0.2 Earnings Alpha | 标准财报点评与精确财务/segment/guidance | 产品 L2；3 Case R2，争取 1 Case R3 |
| `REL-PROD-003` | FIN 0.3 Review & Memory Beta | exact-version review、修订复用、follow-up、选择性 refresh | 稳定 R3；一个 bounded R4 sequence |
| `REL-PROD-004` | FIN 0.4 Cross-sector Beta | SaaS、银行、消费/工业 Sector Pack 校准 | 跨行业 R2；验证泛化 |
| `REL-PROD-005` | FIN 0.5 Enterprise Pilot | Data Room、私有材料、RBAC、审计、跨产物一致性 | L3 受控试点 |

Watchlist/Monitoring 在 Case/Memory 稳定后进入主发布；Research-to-Quant 继续作为 assisted experimental track，不进入最早主发布关键路径。

## 7. 下一上线版本

下一项真正的产品上线版本固定为：

```text
REL-PROD-001
FIN 0.1 Internal Alpha
P36 / AI Infrastructure Research Vertical Slice
```

它在 `REL-FND-001 / POINT01_FOUNDATION_ALPHA_CONTRACT_RUNTIME_PROOF_COMPLETE` 后获得仅限 fixture/shadow/internal development 的开发准入。FIN 0.1 Internal Alpha 的发布准入仍由 P07.5 的 RG1-RG5 决定；其中 RG1 必须补齐 entry→adapter→subprocess→clean-child identity、一次 bounded operational vertical run 与 actual/oracle/reviewer/Workbench 结果。它只面向内部 analyst 和 senior reviewer，不面向客户、不承诺生产 SLA，也不改变 legacy global authority。

产品目标不是只回答一个 AI 基建问题，而是让内部 analyst/senior 使用一套真实工作台完成一次可创建、可运行、可补查、可审阅、可追溯、可回滚的深度研究任务。完整产品闭环包括：

1. Dashboard / Task Center 创建 ResearchCase，形成 Objective、as-of、source、budget 和 reviewer 合同；
2. Lead 编译并由用户审阅 DecisionSurface；
3. durable workstreams 执行 RAG/SQL/graph/market/official web 取证并暴露状态、失败和 typed stop；
4. Evidence Workbench 与 Numeric Drawer 展示 accepted/context/rejected/gap、citation、row/unit/period/formula；
5. Workpaper 按研究判断组织 domain judgment、counter-thesis、What-Would-Change 和 gap；
6. Repair Queue 把缺口路由回来源 owner，Lead 负责 triage，Writer 不补源；
7. LeadReview 冻结 DecisionSurfacePack/WriterBrief，Writer 生成内部 HTML/Markdown；
8. Senior 在 exact artifact version 上 review，并可从 material claim 双向追到 evidence/tool/parser/numeric/promotion。

P36 的六条 AI infrastructure 链是 Anchor Case 的必选 `cell families`，不是产品功能列表，也不是固定六格。Lead 应使用 universal archetype + AI infra sector pack + bounded case delta 编译 10-20 个实际 cells，目标 12-16；planning checkpoint 允许 reviewer 裁剪、拆分或增加 cells，但不得静默删除 risk/counterevidence、material numeric sanity 和 writer boundary。

前端是 FIN 0.1 的必交付能力。它从 Point 02 的 Task Center/Case/Plan shell 开始，随 Point 03-06 逐步增加 Evidence、Numeric、Workpaper/Repair、Deliverable/Review/Trace，而不是等研究后端完成后一次性包装。JSON/API 继续用于 replay/debug，但不能替代 analyst/senior 的可操作工作台。

正式功能、surface、前端动作、TECH owner 和验收矩阵见 `FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX_20260717.zh-CN.md`。首版明确不扩大到 Data Room、Watchlist/R4、Research-to-Quant、全行业 pack、企业 SSO 或全格式交付。

## 8. 发布阻断与允许延后

必须阻断当前版本：

- accepted evidence 不支持 material claim；
- material number 的 entity/period/unit/row/formula 错误或不可复算；
- Writer 自行补源或 supervisor supplement 冒充 runtime evidence；
- material claim 无 provenance；
- canonical/legacy 双 authoritative write；
- 当前纵向路径不可运行或没有 rollback；
- 权限绕过、秘密泄露或真实数据破坏。

允许明确披露后延后：

- 未覆盖所有行业、provider、artifact 或负例；
- 缺完整 SSO/SCIM/KMS/DLP；
- UI 尚未达到客户级视觉完成度；
- 不抵抗拥有数据库文件任意权限的恶意管理员；
- commercial/undisclosed data gap；
- 完整多格式一致性和持续 monitoring。

## 9. 产品发布原则

一个版本只有同时满足以下条件才可发布到目标通道：

- 目标用户能够完成指定工作；
- Anchor Case 达到声明的 R level；
- hard blockers 为零；
- 已知缺口有 typed status、owner 和后续版本；
- rollback 可执行；
- 发布说明没有把 fixture、manual supplement 或旧 runtime 能力写成当前版本能力。

“还能继续优化”不是延迟发布的理由。发布后由真实 dogfood、reviewer edit、failure attribution 和使用时间决定下一列车优先级。
