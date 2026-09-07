# FIN 0.1.3 S3 — Multi-Agent Preview R5 分析片段续跑零调用门

日期：2026-08-20

状态：`R5_analysis_checkpoint_successor_zero_call_pass / one_continuation_authorized / live_not_executed / S1_and_S3_false`

## 1. 这次修的不是 DeepSeek 输出字段

R4 的 Research Lead 已经读取六份独立 Specialist 计划并形成 9,932 字可见分析，只是在第 11 个协调问题中途达到输出上限。原 Runtime 把分析阶段当成一次性调用：即使大部分工作已经完成，也只能终止整个节点，不能保存进度、告诉同一 Agent 还缺什么，再从缺失处继续。

本轮把这项缺口实现为 provider-neutral 的分析片段续跑能力。它不改 S1／S2 数据，不新增 Evidence／NumericFact，不扩大报告权限，也没有用 Harness 补写 Lead 观点。

## 2. 实际实现

1. 将 R4 request／response capture、digest、`finish_reason=length`、9,932 字草稿摘要和已完成／未完成章节绑定为不可变 `AnalysisFragmentCheckpoint`。公开 checkpoint 只保存摘要、长度和 capture ref，不复制原始草稿。
2. 本地只判定结构完成度：`accepted_agent_ids`、`accepted_facets` 已完成，`coordination_questions` 部分完成，`expected_information_boundaries`、`stop_conditions` 缺失。
3. 为同一 Research Lead 生成可行动 `FeedbackReceipt`，只允许补齐三个未完成输出；禁止重复前两节、改变 Case／as-of／authority 或创建事实。
4. 续写提示只包含已保存片段和缺失字段，不重新发送 R4 的六角色完整原始上下文；原上下文 sentinel 泄漏 mutation 会失败。
5. 最多一次 continuation。若仍被截断、缺字段、重复已完成字段或 receipt 漂移，节点再次 fail closed，不自动进入第二次续写。
6. 只有原片段与合格续写合并后，才进入既有 non-thinking strict submission；analysis draft 仍不能晋升业务事实。
7. 成功和失败结果都记录 checkpoint、续写 proof、分析／续写／submission 调用数、SessionEvent、反馈与 resume receipt。

## 3. TokenBudgetBasis

续写节点采用 `reasoning_effort=low`、`max_tokens=4000`。依据不是省钱或追求速度，而是任务已经从“综合六份计划”缩小为“补齐三个明确缺失字段”：输入只有已保存草稿和结构化反馈，输出格式固定，且禁止重做已完成部分。若一次仍不能完成，按无进展停止，不通过提高预算或无限续写掩盖问题。

## 4. 零调用证明

- R4 partial draft 的 capture、内容摘要和长度全部重新校验；任一漂移均拒绝恢复。
- fake 全链证明一次 continuation 后可以进入严格提交。
- 缺失章节、重复已完成章节、错误完成清单、第二次 continuation、原始长上下文重发和 checkpoint 篡改均 fail closed。
- 定向回归：`59 passed`；全仓回归：`850 passed`；活动基线为 184 Python／8 frontend／27 Runtime／0 forbidden；秘密扫描 7,382 文件／0 finding；0 模型、0 网络、0 付费工具、0 Candidate promotion。

零调用结果：`configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_R5_analysis_successor_zero_call_result_v1_0.json`。

## 5. 边界和下一步

本轮只证明工程上可以从 R4 的真实失败片段恢复，并让同一 Agent 获得一次可验证反馈后继续。它不证明 Research Lead 自然续写成功，也没有生成六份工作底稿、跨角色挑战、Evaluator 结果或 Writer 报告；S1、S3、泛化、qualified-human、Workbench 发布和 release 仍为 false。

下一步是在干净、已推送实现提交上执行 Project OS preflight，签发唯一一次 R5 authority，并真实运行该续写。若后续节点暴露新失败，按数据／工具、Harness、Agent 编排、模型判断和 Evaluator 五个平面归责，保留失败后从最早责任层继续，不回到逐字段修补。
