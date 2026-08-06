# 647 — FIN 0.1.3 S3-01 动态 DecisionSurface 与 reviewer revision

日期：2026-08-06

## 结果

`013-S3-01` 达到 `engineering_pass`。本轮没有把历史 P36 10-cell shadow fixture 直接升格，也没有另造一套 planner；实现复用 canonical `CellCompositionEngine` 与 `DecisionSurfacePlanningService`，由当前 S1 governed retrieval pack、S2 公司专属研究合同和 case delta 编译三案动态研究面：

- DELL：13 Cell；
- MU：12 Cell；
- NVDA：13 Cell；
- 三案均覆盖 6/6 P36 family，即五条产业链 family 加跨链 counterevidence/What-Would-Change family；
- 每个 Cell 均有本案问题、owner、EvidenceSlot、stop rule、What-Would-Change、dependency 和 current/planned evidence binding；
- DELL、NVDA 的第 13 Cell 由当前 S1 typed gap 触发，MU 无 typed gap 因而保持 12 Cell，证明结果不是固定标题清单。

Reviewer 零调用证明覆盖 inspect、prune、split、add、return 和 immutable revision。普通 Cell 可裁剪、拆分或新增，但 material numeric sanity、risk/counterevidence 和 Writer boundary 不得静默删除；family coverage、cross-case binding、empty WWC、stale upstream 等 mutation 均 fail closed。

## 根因修复

入口审计发现 canonical composition 会校验 archetype 含 What-Would-Change，却未把它投影进 `DecisionCellSeed`。这会造成 archetype 与计划产物的假一致性。本轮在 shared composition 层补齐 WWC 投影并增加回归，没有用 renderer 或 fixture 手工补值。

历史 S0-02 source-hash 测试因此继续作为不可改写的 historical assertion deselected；旧决策和哈希未被更新。新的 S3-01 decision/program digest 是当前修复权威。

## 验证与边界

Focused：`12 passed`。S0–S3 current successor：`207 passed / 1 historical assertion deselected`。模型、Provider、网络、来源和业务 Run 均为 0。

S3-01 只证明动态规划和 reviewer revision，不证明 12–13 个 Cell 已经获得高质量判断。历史 10-cell shadow evidence placeholder 没有被提升；新增计划 slot 没有 Evidence 时仍是 `planned_request`。下一项是 `013-S3-02`，负责公司专属 Claim、非重复 gap 与可观测 What-Would-Change；Lead、Writer、Verifier、八维质量、产品验收和 release 仍未开始。
