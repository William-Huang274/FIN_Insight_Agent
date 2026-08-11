# 122 - P38 Next-phase implementation discussion draft

记录时间：2026-07-11

## 用户要求

在 Canonical / Legacy 工程交接完成后，将下一阶段新需求和新功能的六步讨论顺序先写入草稿文档，后续再逐项修改和对齐进度。

## 完成内容

新增：

- `docs/architecture/repository/NEXT_PHASE_IMPLEMENTATION_DISCUSSION_DRAFT_20260711.zh-CN.md`

草稿固定以下讨论顺序：

1. 确定第一个 runtime migration slice；
2. 定义代码目录、SQL、API、event 和 adapter 的真实实现边界；
3. 裁决旧模块直接复用、adapter、只读兼容、supersede 或 archive；
4. 将 TECH_01-11 转成有依赖的 backlog 和 acceptance gates；
5. 决定 Agentic Research、Search、Context、Harness、Workbench 等落地顺序；
6. 确定首个 calibration case、fixture、shadow run 和 cutover 标准。

首个讨论议题暂定为 Control Spine 与 DecisionSurface Spine 的落地关系。本文仅为 discussion draft，不修改 PRD/TECH、canonical cutover 状态或 runtime 写路径。
