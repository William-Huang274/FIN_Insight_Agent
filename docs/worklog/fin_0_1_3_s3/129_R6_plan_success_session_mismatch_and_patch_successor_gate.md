# FIN 0.1.3 S3：R6 计划成功、Session mismatch 与剩余 patch 门

日期：2026-08-23
状态：`R6_natural_plan_valid / local_session_lineage_fail / one_patch_successor_zero_call_pass`

## 1. R6 实际发生了什么

R6 只执行了第一项 planning call：

- DeepSeek 读取五份完整 FeedbackReceipt；
- 对五项 L1/L2 问题逐条承认，给出正确的降级、改期、假设恢复、指标拆分和机制去具体化方案；
- 提交单一 strict tool call，`prompt=5,902`、`completion=3,129`，其中 reasoning `2,021`；
- Plan 与 PlanDelta 均通过业务合同；
- 0 检索、0 S1/S2、0 新 Evidence、0 Candidate promotion、0 retry。

随后本地 `apply_accepted_plan_delta` 返回 `runtime_plan_delta_session_mismatch`，第二项 patch call 没有执行。R6 public／private result、请求和响应 capture 已按 exact-once 留存，output identity 不复用。

## 2. 根因

FeedbackReceipt 与 PlanDelta 被编译给新 repair session；runner 却复制 R3/R5 的旧 research session 和事件历史，再把新 PlanDelta 应用到旧 session。Canonical Runtime 正确 fail closed。

原零调用 proof 的缺陷是只验证：Plan 合同能编译、PlanDelta 能编译、受控 patch 能合并；没有真实调用 `create_agent_session` 和 `apply_accepted_plan_delta`。这是组合接缝漏测，不是 DeepSeek 不遵循合同。

## 3. 结构修复与复用边界

- 已完成 research session 不修改；新建 repair successor session，继承 Case／version／as-of／objective；
- repair session 与五份 FeedbackReceipt、PlanDelta 使用同一个 session ID；
- R6 已验证的自然 Plan 通过 private result、request/response capture、event sequence 和 digest 重新资格化，0 次重复模型调用；
- 新零调用 proof 真实执行 session_created→plan_bound→feedback→PlanDelta submitted/accepted→受控 patch；
- 漏失／漂移的 R6 failure、plan、context、capture 或 event 任一项都会拒绝复用。

零调用结果：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_semantic_patch_successor_zero_call_result_v1_0.json`。

## 4. 剩余权限

原两节点语义修复预算已经消费 planning call；只剩一次 non-thinking patch call。它不是第二轮内容修复，也不能重新分析、检索或生成计划。Patch 合同通过后仍需独立 L1／L2 与内容质量审查；失败后不再自动进入新的 DS 专用修补。

## 5. 工程复证

- 定向 Session／Feedback／Project OS：`95 passed`；
- 全仓：`1098 passed`，仅保留 2 条既有 SWIG deprecation warning；
- `compileall`：通过；
- active baseline：`207 Python / 8 frontend / 5 runtime detectors / 28 runtime resources / 0 unresolved / 0 forbidden`；
- repository secret scan：`7,722 files / 0 findings`；
- `git diff --check`：通过。

该结果证明的是 R6 自然计划能够在不重跑 planning 节点的前提下，经过 capture-bound 资格判断进入新 repair session，并完整穿过 PlanDelta 与受控 patch 接缝；它仍不证明自然 patch 内容或 L1／L2 已通过。
