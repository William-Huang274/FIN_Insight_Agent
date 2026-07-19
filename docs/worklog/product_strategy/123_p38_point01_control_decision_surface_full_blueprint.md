# 123 - P38 Point 01 Control / DecisionSurface full blueprint

记录时间：2026-07-11

## 用户要求

第一点不能只有最小落地方案，需要先给出完整技术实现路线；后续 1-6 点也都应先形成完整蓝图，再根据实际情况修改。

## 完成内容

新增：

- `docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md`

规划结论：

- 工程上先实现最薄 Control Kernel；
- 第一条完整业务 migration slice 是 DecisionSurface Planning Shadow Lane；
- shadow calibration 通过后，先做 lane-scoped DecisionSurface planning cutover；
- 再扩展 Control Spine 承载 Evidence / ReAct execution；
- 后续逐步迁移 Evidence、Repair、Domain、LeadReview、Writer、Workbench，并最终关闭 legacy writes。

完整草稿覆盖：M0-M7、第一阶段九个 canonical objects、最小 vertical slice、目录/SQL/API/event/adapter、test/eval、observability、安全权限、rollout/rollback、风险、Definition of Done 和八项待决策问题。

同时更新总讨论草稿，要求后续 Point 02-06 第一版都必须包含目标架构、MVP、完整路线、迁移、测试、观测、验收和退出条件，不能只做 MVP 后再补整体设计。

## 边界

- discussion draft；
- 未批准实施；
- 未修改 PRD/TECH；
- 未切换 runtime；
- 未运行 paid model 或 full-chain。
