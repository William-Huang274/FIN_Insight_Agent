# FIN 0.1.3 S3 submission successor R4 本地返修合同失败与 R5 精确前沿

时间：2026-08-23

状态：`R4_terminal_preserved / six_workpapers_and_Lead_R1_reconstructable / R5_zero_call_proven / R5_live_authority_pending`

## R4 真实完成了什么

R4 从 R3 的 Cash workpaper 前沿继续，新增 9 次 DeepSeek Provider 调用，全部 HTTP 200、`finish_reason=tool_calls`、0 retry。Cash 与 Supply 的底稿、Supply 唯一一次 current S1/S2 补证回合以及 Lead R1 均已完成。加上 R3 的 8 份可复用 capture，六份 Specialist workpaper 和第一轮 Lead 决策可由 17 份 immutable capture 完整重建。

Lead R1 只接受三项当前证据内可修的高重要性挑战：

- Cash 必须把公司级经营现金流与 AI 产品级现金转换分开；
- Operating 必须避免把 ISG 分部经营利润冒充 AI 服务器利润；
- Value 必须把价值获取判断与“毛利率下降、费用率下降推动经营利润率改善”的真实桥接关系相协调。

需要新增资料的挑战继续留在 Evidence Gate，没有被 Writer 或本地 renderer 偷补成事实。

## 失败发生在哪里

R4 在第一次 role repair Provider 调用之前停止。`compile_workpaper_repair_context` 已正确生成带 `prior_workpaper` 与 `accepted_feedback_refs` 的 repair context，但 `compile_workpaper_submission_view` 仍只接受基础 workpaper context schema，因此以 `dynamic_single_unit_workpaper_submission_context_invalid` fail closed。

这是本地 Harness 的合同投影漂移，不是 DeepSeek、S1/S2、来源、网络、TokenBudget 或金融研究内容失败。R4 public/private terminal、全部 capture 和准确失败前沿保持不可变：

- public result：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_live_result_v1_3.json`
- public result digest：`af5fb33c752b378a0dd366ff0bb874314175c281ce7181dd679fb67db5c39d16`
- private terminal SHA-256：`61d6df6258b3b807d16808788b6ca98b49ff623bdc05976af6b0f8ba52156d4d`

## 结构修复与 R5 零调用复证

提交视图现在显式接受基础 context 或 repair context；repair context 必须通过自身 digest 校验，并必须携带有效的 prior workpaper 和 accepted feedback。模型可见修复视图不再丢失 Lead 已接受的修复范围，本地仍禁止新增 Evidence、NumericFact、关系或跨角色改写。

R5 零调用 proof 使用 17 份 capture 重建六份 Specialist workpaper 和 Lead R1，重新选择且仅选择上述三份 role repair。首个新 Provider 前沿精确为 `cash-conversion-repair-r1-draft`；0 模型、0 网络、0 retrieval、0 paid tool call。公开 proof：

`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_zero_call_result_v1_4.json`

result digest=`c7976f51c207e39aa79cb6f53bf186cb08161789fa3486641ce6a81ee3271721`。

R5 的剩余自然拓扑严格为 8 次：Cash／Operating／Value 各一份自然 repair draft 和一次 strict submission，共 6 次；Lead R2 自然协调与 strict submission，共 2 次。为按当前代码重建 R4 的 Supply 权威，允许确定性重放 R4 已批准的同一条 Supply S1/S2 request；这不是新增研究方向、不会访问外网或晋升 Candidate。除此之外为 0 新 S1/S2 路线、0 retry、0 外源、0 Candidate promotion、0 fallback。已经完成的 17 个 Provider 节点不得重跑。

工程门为定向 `24 passed`、全仓 `1127 passed`（仅 2 条既有 SWIG deprecation warning）、compileall、pyflakes、active baseline `210 Python／8 frontend／5 detectors／28 Runtime／0 forbidden`、928 份 config、8 份 Project OS JSONL／1,005 行、7,767-file secret scan／0 与 diff check 全部通过。

## 边界与下一门

当前只证明“精确从返修前沿续跑”的工程资格。尚未证明三份返修内容合格、Lead R2 决定可接受、六角色整体 L1、八维内容质量、Writer、S3、MU/NVDA、异质留出、Workbench publication 或 release。

下一门是全仓验证、clean commit／push、current decision-bound Project OS preflight 和一份 exact-once R5 authority。R5 完成后必须先独立做 L1 与内容质量审查；只有内容通过才进入 Writer。
