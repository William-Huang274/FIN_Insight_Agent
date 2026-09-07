# FIN 0.1.3 S3：DELL 动态单元语义反馈修复零调用门

日期：2026-08-23
状态：`semantic_feedback_plan_patch_zero_call_pass / clean_execution_authority_pending`

## 1. 为什么要做

R5 的动态研究和严格底稿合同已经通过，但金融判断没有通过。五项错误都不是“再找一份资料”能解决，而是 Agent 把输入中已经标明的管理层表述、历史背景、未证假设和公司总量写成了更强的当前产品结论。若只在 Prompt 中补一句禁止项，下一次仍可能换一种表述重复越权。

## 2. 本轮实现

- `FeedbackReceipt` 现在可以完整保留独立审计给模型看的失败原因、允许动作和禁止解释；
- 新增统一语义修复 Runtime，把五项 finding 编译为同一 Agent 的 feedback bundle；
- Agent 必须先提交覆盖五条反馈的修复计划，Runtime 再编译并接受 `PlanDelta`；
- 第二节点只提交 `thesis / sourced_claims / mechanism` 三个修复表面；其余七个工作底稿字段按 digest 锁定并由本地合并；
- 新引用、新检索、新 Evidence、Candidate promotion 和 product pointer mutation全部禁止；
- 请求／响应仍 capture-first，公开 telemetry 不重复保存 Tool arguments；传输或校验失败时给每个已请求 attempt 补齐 typed failed 终态；
- 修正历史 R5 runner 的 double digest。R5 结果保持不可变，修复上下文显式识别旧 digest 风格；未来结果恢复为 Validator 的单一 canonical digest。

## 3. 零调用结果

结果：`semantic_feedback_plan_patch_loop_zero_call_proven`。

- 五项审计 finding 全部成为可行动 FeedbackReceipt；
- 同一 Agent 的 PlanDelta 精确覆盖五项反馈；
- 只允许三个修复表面变化，七个锁定表面逐值相同；
- 漏掉一项反馈、使用错误修复动作、加入此前未用引用均 fail closed；
- 模型／网络／检索／Candidate promotion／产品指针修改均为 0。

零调用结果：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_semantic_repair_zero_call_result_v1_0.json`。
Scope decision：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_semantic_repair_scope_decision_v1_0.json`。

## 4. 权限边界

下一次 live 最多两次 Provider 调用：一次 thinking=max 的 feedback→PlanDelta，一次 non-thinking 的严格 patch。它复用 R5，不执行 S1／S2、不增加资料、不重跑动态研究、无 retry。两节点 TokenBudgetBasis 分别依据反馈规划的语义复杂度和 patch 合同容量设置，不能以省钱或速度删减必需工作。

即使合同通过，状态仍只能是 `assessment_pending`。只有独立 L1／L2 与内容质量通过，才可讨论动态多 Agent；若同类语义越权仍然存在，不再进入逐字段 DeepSeek 专用修补。

## 5. 完整工程门

- 定向：`91 passed`；
- 全仓：`1094 passed`，仅 2 条既有 SWIG deprecation warning；
- `compileall`：通过；
- active baseline：`207 Python / 8 frontend / 5 runtime detectors / 28 runtime resources / 0 unresolved`；
- repository secret scan：`7,718 files / 0 findings`；
- diff check：通过。

因此可以进入“干净提交 → repository-aware preflight → fresh authority”阶段；这仍不代表自然修复或内容验收通过。
