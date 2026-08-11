# P38 VT1 P02.4 Vertical Contract Increment

## 1. Decision

P02.3/P02.4 的第一轮 worker 没有改代码。它发现当前 P02.0 v1.1 只冻结了 `compileDecisionSurface`、`getDecisionSurface` 和 `reviewPlanningCheckpoint`，但没有冻结 `ReviseDecisionSurfaceCommand`，`DecisionSurfaceCellView` 也不能承载 `EvidenceSlot` 与 `what_would_change`。现有 `RuntimeFacade.commit_decision_surface_bundle()` 还强制要求 `WorkUnit/Attempt`，会错误地把 P02.5 执行生命周期提前拉入 P02.4。

这不是继续修 Point 01，也不是复核发现的新防御性要求，而是 P02.4 backlog 已明确要求、但 P02.0 基线遗漏的产品接口。处理方式是一次最小版本化合同增量，不重开 P02.0，不改写 P02.0 v1.1 closeout，不新增 gate 或 package family。

## 2. Frozen Increment

Authority artifact:

- `configs/releases/point02_p02_4_vertical_contract_increment_v1_0.json`
- canonical digest: `83319c49d2c91616503e83a2fce31ff2837792ecbbdb6015aaa08f4c85cfffb7`

它固定：

- P36 三个首批 cells：需求真实性、价值/利润捕获、瓶颈与反证；
- 每个 cell 的 question、owner、materiality、stop rule、what-would-change 和两个 required EvidenceSlots；
- compile、revise、accept/return、get 的 exact command/query 边界；
- immutable contract/cell/slot version lineage；
- 独立 `PlanningCheckpointVersion`，不依赖 WorkUnit/Attempt；
- fixture/shadow/internal 权限与零网络、零模型、零 paid、零真实业务写入边界。

## 3. Architecture Boundary

批准的路径为：

`API planning routes -> Workbench PlanningService -> RuntimeFacade -> CanonicalStore`

复用现有 Case-scoped append-only store transaction 与 DecisionSurface/Cell/EvidenceSlot 表；新增 `canonical_planning_checkpoint_versions`。禁止复用会完成 WorkUnit/Attempt 的旧 bundle writer，也不改变 `CaseControlSummaryVersion.planning_authority`。

## 4. Product and Governance Delta

Product capability delta：解除 P02.4 真实实现阻塞，使浏览器能够实现 compile -> revise -> version -> accept/return -> refresh/reopen 的完整计划流。

Governance cost delta：新增 1 个增量合同和 1 组 5-test contract checks；没有新增 milestone、gate family、package family 或测试矩阵。

验证：增量合同加 P02.0 v1.1 regression 共 `11 passed`。

## 5. Boundary

该增量只授权 P02.3/P02.4 当前 VT1 internal fixture 实现。P02.5、RG1、operational qualification、FIN 0.1 release 和 production readiness 均未授权；`legacy_global_authority=retained`。
