# 072 Case Truth semantic canary R1：低思考仍耗尽推理预算

日期：2026-08-17

## 结果

绑定 clean/synced commit `2f86056b02572894fdb4c5bdc8dee49d4981f7a3` 的唯一 R1 已执行。请求只包含 R7 不可变的 15 个 claim surface、紧凑 Case Truth view 和一个 strict reconciliation tool；不检索、不 embedding、不修文、不生成报告，0 retry/fallback/protocol switch。

Provider 网络与响应均正常：HTTP 200、完整 JSON、无截断。请求实际携带 `thinking=enabled`、`reasoning_effort=low`、`max_tokens=8000`。响应使用 `14,576` prompt tokens 和 `8,000` completion tokens，其中 reasoning tokens=`8,000`；`finish_reason=length`，可见 content 为空、Tool Call 为 0。因此终态为 `model_gateway_reasoning_budget_exhausted`，本地 semantic validator 未执行。

## 判断

这不是 DeepSeek 连通性、strict schema transport 或 Case Truth 确定性合同失败。它证明“同时读取全案 truth view、分析 15 个语义面、再一次性交严格 JSON”仍是一个过密节点；即使 profile 标成 low thinking，当前 strict-beta 路径也没有在 8k 内产生可见交卷。

不能简单提高到 16k 再试，也不能改成关键词规则。项目此前已证明片段上下文与分析／交卷分离可以解决同类非收敛；本轮应复用这一通用模式：

1. 按 cell 或受影响 surface 编译有 digest 的 claim-document slice；
2. analysis 节点只做语义解释并列出精确 alias/state，不承担 Tool Call；
3. non-thinking submission 节点只把已形成的分析映射为严格 Tool Call；
4. Harness 聚合 slice receipts，并继续用完整本地 Case Truth 权威做最终校验；
5. 先对 Operating／Counterevidence 两个已知受影响 cell 做 successor canary，再决定是否扩到其余 cell；不重跑研究 analysis、Planner、S1/S2 或报告。

R1 保持不可变。它没有产生语义分类，因此不能记为内容失败或模型合同不遵循；natural semantic extraction、R7 repair、DELL 五单元、泛化与 S3 均仍为 false。
