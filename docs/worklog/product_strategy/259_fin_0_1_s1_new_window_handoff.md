# 259 FIN 0.1 S1 新窗口交接

日期：2026-07-19
状态：`handoff_ready`

## 问题

用户准备在新窗口继续 FIN 0.1，需要把长对话中的产品决策、执行权威、当前事实、Git 边界和 S1 第一项任务压缩成可独立执行的仓库交接说明。

## 决策

以 `docs/project_os/thread_handoff_20260719_fin_0_1_s1_program_execution.zh-CN.md` 作为新窗口入口。当前不直接开始 Agent 实现，只允许从 backlog 的 `S1-T01` 开始，先冻结 D02-D14 到现有代码的适配图和唯一 Runtime/API/UI 写入主线；S1 完成后必须停在真实模型授权边界前。

同时修正 `configs/releases/fin_ia_0_1_code_mainline_manifest_v1_0.json` 的 active authority 指针：ReleaseContract 从 v1.2 更新为 v1.3，唯一 backlog 改为 program release backlog v2.0，并登记 FeatureScope v1.1。

## 结果

- 交接覆盖当前产品事实、执行权威、代码主干、S1-T01 至 T06、S2-S5 固定方向、修复纪律、不可自动授权范围、Git 状态和新窗口首轮指令。
- 当前没有模型、网络、产品测试、业务写入或 full-chain 执行。
- 当前未自动暂存或提交文件。

## 后续

新窗口先验证交接中的最小权威集合和 Git 状态，再执行 S1-T01。任何真实模型、provider、网络、预算或 S2 工作均需另行授权。
