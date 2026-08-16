# DeepSeek strict-pattern live canary R1

日期：2026-08-17

## 执行目的

只验证 DeepSeek Beta strict Tool 传输是否真的接受 provider 投影后的共享模型文本 `pattern`。输入刻意包含 `10-Q` 与 `FY27 Q1`，但没有任何金融 Evidence，也不执行 DELL Judgment。

## 真实结果

- run：`FIN013-S3-DEEPSEEK-STRICT-PATTERN-R1`
- status：`completed_deepseek_beta_strict_pattern_qualified`
- Provider 返回 `finish_reason=tool_calls`，Schema 被接受；
- prompt / completion / total tokens：`591 / 69 / 660`；
- 最终 atom 没有数字、filing identifier、期间、单位、URL 或内部引用；
- 本地完整模型文本合同再次通过；
- model / transport：`1 / 1`，retry / fallback：`0 / 0`；
- financial Evidence / product publication：`0 / 0`。

原始请求、响应与完整输出已按 capture-first 保存在本地受限路径；公开结果只保存 atom digest，不公开模型文字。

## 结论与边界

DeepSeek Beta strict transport 对本项目共享 `pattern` 的资格成立，证明 R3 的已知 surface failure 可以在 Provider 解码时提前约束，而不必继续增加逐字段 Prompt 补丁。它仍不是金融内容验收：完整 Judgment Schema、value/counter 业务判断、五单元综合和研报质量尚未证明。

下一项只允许零调用建立节点 successor：完整校验 R3 capture，复用 demand、operating、cash 三份有效 Judgment 与 value/counter 两份成功分析草案；最多只为 value/counter 重新交卷，并在五份 Judgment 均有效后执行综合分析和综合交卷。
