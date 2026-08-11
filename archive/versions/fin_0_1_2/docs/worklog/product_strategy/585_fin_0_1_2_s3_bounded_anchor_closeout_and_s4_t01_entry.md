# 585 — FIN 0.1.2 S3 有限锚点关闭与 S4-T01 入口

日期：2026-08-04

## 问题与 Owner 决定

S3-T04 已完成零模型 delivery surface 收敛，但 frozen input 的 promoted Evidence coverage 仍为 `0/3`。现有 PRD 又把 Retrieval readiness、Agentic Search、Evidence promotion 与 natural-Case research 分配给 S4-T02/T03/T04，形成“S3 要先有 Evidence 才能进 S4、但 Evidence 又只能在 S4 产生”的循环门禁。

Owner 回复“批准”，接受首选处置：

- S3 以“有限 frozen-input Runtime 与 verified delivery anchor”通过并关闭；
- 该通过不等于 current source-grounded NVDA R2；
- prior product rejection、0/3 Evidence 和 immutable exact evidence 不改写；
- current source-grounded NVDA R2 移到 S4-T04，在 S4-T02/T03 完成 evidence qualification 后验收；
- S4 进入 T01，但本轮只冻结入口/计划，不执行 T01 implementation 或 T02 retrieval。

## 完成的工作

- 新增 Owner 决定：`configs/releases/fin_ia_0_1_2_s3_t04_owner_stage_boundary_realignment_and_s3_closeout_v1_0.json`；
- 新增 S4 source StagePlan：`docs/architecture/repository/FIN_0_1_2_S4_EVIDENCE_TO_WORKBENCH_STAGE_PLAN_20260804.zh-CN.md`；
- 新增机器可读 S4 entry/T01 plan：`configs/releases/fin_ia_0_1_2_s4_evidence_to_workbench_stage_entry_and_t01_plan_v1_0.json`；
- 新增 current projection v2.35，更新 program backlog、产品重基线、S3 source plan 与 Project OS；
- 新增合同测试，证明 Owner scope acceptance 不会被误写成 product acceptance，历史 FIN 0.1 S4 不会被当作当前证明，T01 未完成且 T02 未进入。

## 结果与边界

- S3=`pass_closed_bounded_anchor_not_source_grounded_NVDA_R2`；
- S4=`entered_T01_started_implementation_pending`；
- current NVDA R2=false；
- promoted Evidence=`0/3`，candidate promotion=false；
- model / Provider / network / source / tool / admission / Run / Artifact / Human Review=`0`；
- 原 replacement exact Runtime `execution-result.json` SHA256 仍为 `7f430356295c558f5158898d069905c3ce6d02b2585e87676c9252ebd5a3568c`；正式 closeout 记录文件自身 SHA256 为 `750d579af96c48c7850d540bd588ce13b3ba9e5c4c22a33c39a88ab6a8baada7`，两者不是同一对象；
- 本轮没有检索、模型实验、paid job 或业务执行。

## 验证

- S3 closeout / S4 entry focused contract：`5 passed`；
- S3-T03/T04 历史证据、Owner rejection、delivery surface 与 S4 后继状态组合回归：`30 passed`；
- 唯一首次失败是旧 S3 测试的后继任务白名单尚未登记 S4-T01；只补充合法阶段后继及其严格状态断言，没有修改 Runtime、Artifact 或 L1/L2–L4 门禁。

## 下一步

`FIN-0.1.2-S4-T01-NATURAL-CASE-ENTRY-AND-EXACT-BINDING-ZERO-CALL-IMPLEMENTATION`

只实现自然 Objective、as-of、预算、三 Cell、source/index snapshot refs 与 fresh identity 的三案 exact binding；完成 mutation、cross-case、nonreuse、permutation 和 current Runtime consumer readback。T01 通过后才可另行进入 S4-T02 retrieval/evidence deterministic readiness。
