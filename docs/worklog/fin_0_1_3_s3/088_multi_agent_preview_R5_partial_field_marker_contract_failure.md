# FIN 0.1.3 S3 — Multi-Agent Preview R5 部分字段续写标记合同失败

日期：2026-08-20

状态：`R5_terminal_failure_preserved / natural_continuation_substantively_complete / Harness_marker_contract_false_negative / submission_not_started`

## 1. R5 实际结果

R5 在干净、已推送提交 `5a780dff...` 和通过的 Project OS preflight 上执行。六份 R3 Specialist 计划未重跑；Research Lead 从 R4 的 9,932 字分析 checkpoint 恢复，只发生一次 continuation 调用。

Provider 返回 HTTP 成功、`finish_reason=stop`，输入 3,063 token，输出 1,106 token，其中 reasoning 仅 39 token，可见内容 5,003 字。模型直接续完被截断的第 11 个协调问题，又补充第 12／13 个问题，随后完整给出 `expected_information_boundaries`、`stop_conditions`，并以精确回执 `COMPLETED_OUTPUTS::coordination_questions|expected_information_boundaries|stop_conditions` 结束。

但本地 Validator 仍返回 `multi_agent_analysis_continuation_semantically_incomplete`，因此 submission、工作底稿、挑战、Evaluator 和 Writer 均未启动。R5 保持 terminal failure，草稿未获得业务权限。

## 2. 真正原因

Continuation Prompt 同时要求：

1. “从被截断的句子原地继续”；
2. “给每个 remaining output 写一个 `OUTPUT::<field>` 标题”。

对一个已经在 `coordination_questions` 字段中间截断的片段，这两条要求互相冲突。若模型先写 `OUTPUT::coordination_questions`，就无法原地补完半句；若直接补完半句，就会缺少 Validator 要求的标题。DeepSeek 选择了业务上正确的连续写法，本地合同却只接受机械标题，因此这是 Harness 的 partial-field／missing-field 语义混淆，不是 S1 数据缺失、检索／排序失败、网络／协议失败、模型不会规划或 token 不足。

## 3. 正确的结构修复

- `missing_required_outputs` 继续强制精确 `OUTPUT::<field>` 标题；
- `partial_required_outputs` 与 missing 分开：v1 只允许一个 partial field，续写必须在第一个 missing heading 前提供非空原地补全文本，不要求重复 partial heading；
- 最终 `COMPLETED_OUTPUTS` 回执仍覆盖 partial＋missing 全部字段；
- 已完成字段标题、漏 missing heading、空 partial continuation、错误回执和第二个 partial field 均 fail closed；
- 使用 R5 immutable response 做零调用 replay，形成“R4 partial＋R5 continuation 已完整”的 merged-analysis checkpoint；
- 下一 successor 从 strict submission 开始，不再付费重跑已经完成的 continuation，也不追认 R5 为通过。

## 4. 五平面归责

| 平面 | R5 判断 |
| --- | --- |
| 数据基建／S1／S2 | 未改变，0 外源网络、0 Candidate promotion；不是本次故障源 |
| Harness | 首要责任；partial 与 missing 使用同一 heading 规则，Prompt 自相矛盾 |
| Agent 编排 | checkpoint、FeedbackReceipt、一次 resume 已真实发生；后续节点因 Harness 拒绝而未运行 |
| 模型 | 实质续写完整，低 reasoning profile 与任务匹配；没有证据表明模型研究能力导致本次失败 |
| Evaluator | 未启动，不能对报告内容或 Multi-Agent 增益下结论 |

## 5. 边界

R5 只证明同一 Agent 能消费 checkpoint 和反馈后自然续写；它没有完成 Lead strict plan、六份工作底稿、跨角色协作、Evaluator 或报告。S1、S3、泛化、qualified-human、Workbench 发布和 release 仍为 false。
