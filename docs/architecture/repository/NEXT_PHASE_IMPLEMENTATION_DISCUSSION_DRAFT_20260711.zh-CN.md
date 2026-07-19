# 下一阶段新需求与新功能实施讨论草稿

日期：2026-07-11

状态：`discussion_draft / not_approved / not_runtime_commitment`

## 1. 文档用途

本文承接 Canonical / Legacy 工程交接基线，用于讨论下一阶段新需求和新功能的工程实现方式。内容尚未批准，不直接覆盖 PRD、TECH_01-11、Canonical Object Registry 或现有 runtime source of truth。

后续每轮讨论应记录：

- 当前议题；
- 已对齐决定；
- 未决问题；
- 对既有 PRD/TECH/canonical objects 的影响；
- 是否需要形成正式 backlog、schema、migration 或 acceptance gate；
- 修改日期和 supersession 关系。

每个议题不能只给最小落地方案。第一版规划必须同时包含：

- 目标架构与最终能力形态；
- 最小可执行 vertical slice；
- 从当前状态到目标状态的完整阶段路线；
- canonical objects、store、API、event、adapter 和 owner；
- source-of-truth、migration、cutover、rollback 和 legacy decommission；
- permission、安全、上下文和 artifact 边界；
- fast/fixture/local-data/model/full-chain 测试与 eval；
- observability、SLO、failure attribution；
- acceptance gates、Definition of Done 和不在范围内事项；
- 暂定假设、待决策项和后续修订记录。

后续讨论可以修改蓝图，但不再采用“只规划 MVP、做到哪里再想完整架构”的方式。

## 2. 讨论顺序

### 2.1 确定第一个 Runtime Migration Slice

核心问题：先迁移 `TaskRun / WorkUnit / Attempt / EventEnvelope` 控制主干，还是先迁移 `DecisionSurfaceContract / Cell / EvidenceSlot / EvidenceRequest` 研究主干。

需要讨论：

- Control Spine 和 DecisionSurface Spine 的依赖方向；
- 是否允许第一阶段只做共同最小合同，但不切换 runtime 写权限；
- 第一个 slice 的 producer、consumer、legacy adapter 和 shadow projection；
- 哪些对象必须同批落地，哪些可以保留 legacy projection；
- 第一个 cutover gate 的范围和失败回滚方式。

当前倾向：Control Spine 与 DecisionSurface Spine 需要共同定义接口，但是否同批切换尚未决定。

完整规划已展开到：

- `POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md`

当前暂定结论更新为：先实现最薄 Control Kernel；第一个完整业务 migration slice 是 DecisionSurface Planning Shadow Lane；通过 calibration 后先做 lane-scoped DecisionSurface planning cutover，再扩展 Control Spine 承载 Evidence / ReAct execution。

### 2.2 定义真实工程实现边界

需要把已冻结对象继续落到工程实现：

- 新代码目录和 package ownership；
- SQL schema、migration 和 transaction boundary；
- API、event envelope 和 artifact reference；
- idempotency、optimistic concurrency 和 stale-write 防护；
- permission snapshot、tenant、license 和 data boundary；
- legacy inbound adapter、canonical service 和 outbound projection；
- replay、resume、fork、repair 和 rollback 行为。

要求：不能只增加 Pydantic/dataclass 名称或 prompt 字段，必须明确存储和状态所有权。

### 2.3 裁决旧模块的去向

对当前模块逐项标记：

- `reuse_directly`：实现和新合同兼容，可直接复用；
- `wrap_with_adapter`：保留实现，通过 legacy-to-canonical adapter 接入；
- `read_only_compatibility`：只允许历史回放或旧 UI 查询；
- `supersede_after_cutover`：新链通过后停止写入；
- `archive_after_verification`：零 active dependency 后归档。

每项裁决需要：现有调用方、目标 owner、信息损失、shadow diff、cutover gate 和 archive 条件。不得按文件名、版本号或静态不可达结果直接删除。

### 2.4 将 TECH_01-11 转成工程 Backlog 和 Acceptance Gates

后续需要建立有依赖关系的工程 backlog，而不是按 TECH 文档顺序机械实现。

每个 backlog item 至少包括：

- canonical object / capability；
- owner TECH；
- upstream/downstream dependency；
- schema、API、event、store 和 permission；
- legacy adapter 与 supersession；
- deterministic fixture；
- trace/provenance；
- product projection；
- acceptance gate 和 maturity evidence；
- 明确不在本 slice 内的边界。

Acceptance 需要区分 contract、fixture、runtime consumption、node-level、artifact、dogfood 和 release，不允许用低层 pass 替代高层 pass。

### 2.5 决定主要能力的落地顺序

待排序能力：

- Agentic Research / Lead control loop；
- Agentic Search / Evidence Tool Planner / Evidence Gate；
- Domain operators / DecisionSurface projection；
- Subagents-as-tools / handoff；
- ContextEngine / context governance；
- Durable Harness / permission / checkpoint；
- Workbench decision-cell review；
- Artifact consistency / release；
- Trajectory eval / self-improvement；
- Watchlist / monitoring。

排序不能只看功能可见度，需要同时评估 canonical dependency、迁移风险、可验证性、旧能力复用率和产品价值。

### 2.6 确定首个 Calibration Case 的验证合同

需要选择首个行业/case，并定义：

- calibration case 为什么能覆盖目标架构风险；
- DecisionSurfaceCell 和 EvidenceSlot fixture；
- legacy output 与 canonical shadow output 的比较方法；
- source、parser、numeric、domain、LeadReview 和 writer 边界；
- supervisor supplement 如何转为 RepairTicket，而不是 runtime evidence；
- shadow run、replay、failure attribution 和 cutover 标准；
- 何时允许 node-level model run，何时仍禁止 paid/full-chain。

当前候选是 P36 AI infrastructure case，因为它已经暴露 retrieval、DB row selection、graph projection、specialist、aggregate、writer 和 Workbench 的跨层问题；是否正式选用尚未决定。

## 3. 首个讨论议题

先讨论：

> Control Spine 与 DecisionSurface Spine 谁先落地，以及第一阶段需要共同实现到什么程度。

需要形成的第一轮输出：

1. 两条 spine 的职责边界和依赖图；
2. 共同最小对象集合；
3. 第一批 legacy adapters；
4. SQL/event/API ownership；
5. shadow-only 与 cutover 的边界；
6. 第一阶段 acceptance gates；
7. 明确暂不实现的能力。

## 4. 当前边界

- 本文是讨论草稿，不是正式实施计划；
- 不新增已批准产品需求；
- 不修改 TECH owner；
- 不改变 Canonical Object Registry 的 `not_cut_over` 状态；
- 不切换 legacy runtime 写路径；
- 不授权 paid model、broad full-chain 或 release run；
- 后续对齐内容先更新本文，再决定是否提升为正式 backlog 或回写 PRD/TECH。

## 5. 修订记录

| 日期 | 状态 | 内容 |
| --- | --- | --- |
| 2026-07-11 | discussion draft created | 建立六步讨论顺序，首个议题固定为 Control Spine 与 DecisionSurface Spine 的落地关系。 |
| 2026-07-11 | point 01 full blueprint v0.1 | 增加所有议题必须先给完整蓝图的规划标准；Point 01 补齐 M0-M7、MVP、对象、SQL、API、event、adapter、test、security、rollout/rollback、DoD 和待决策项。 |
| 2026-07-17 | release operating model accepted | 后续不再按 TECH/Point 横向铺开；先冻结 consuming release、L/R 目标、风险和四周 timebox，再反推 Point。Point 01 只服务 Foundation 0.1，下一产品版本固定为 FIN 0.1 Internal Alpha。 |

## 6. Release-Driven Implementation Order（2026-07-17）

此前六项讨论仍有效，但执行顺序改为由 ReleaseContract 驱动：

```text
ProductReleaseIntent
 -> ReleaseContract
 -> required vertical outcome
 -> consuming Point plans
 -> TECH owner child specs
 -> implementation / eval / release
```

每个后续 Point 必须先回答：

- `consuming_release_id` 是什么；
- 对目标用户工作增加什么可观察结果；
- 目标产品成熟度和 Case R level；
- 本 Point 的 `skeleton / fixture / full / calibrated` 分别证明什么；
- 哪些问题是当前版本 blocker，哪些进入 deferred backlog；
- 最多两轮 repair 后如何 stop/defer；
- 最终 milestone closeout 如何被 consuming release 使用。

Point 01 只被 `REL-FND-001 / Foundation 0.1` 消费。它关闭后不直接表示 FIN 产品达到 L2，而是允许 `REL-PROD-001 / FIN 0.1 Internal Alpha` 启动。Point 02-07 的拆分顺序由 FIN 0.1 的完整产品工作流反推：Dashboard/Task Center/Case/DecisionSurface -> Evidence -> Parser/Numeric/Promotion -> Workpaper/Domain/Lead/Repair -> Writer/Workbench/Human Review/Provenance -> Dogfood/Release。P36 六条产业链是 Anchor Case mandatory cell families，不是产品功能清单。

正式规则见 `RELEASE_OPERATING_MODEL_20260717.zh-CN.md`、`POINT_EXECUTION_PLAN_TEMPLATE.zh-CN.md` 和 `RELEASE_FIN_IA_0_1_EXECUTION_PLAN_20260717.zh-CN.md`。

2026-07-17 scope correction：Point 02-07 child plans 必须逐项绑定 `P001-F01`-`F15`，并引用 `docs/product/FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX_20260717.zh-CN.md`；只完成 P36 memo 或六个预设 cells 不构成 FIN 0.1 的 L2 产品 closeout。
