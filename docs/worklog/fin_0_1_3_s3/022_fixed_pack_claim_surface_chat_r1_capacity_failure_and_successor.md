# FIN 0.1.3 S3 fixed-Pack Claim Surface Chat R1 失败与 successor

日期：2026-08-15

状态：`R1 terminal_failed_no_retry / judgment_not_materialized / structural_successor_required`

## 发生了什么

本轮在 clean/synced commit `e65ffef7` 上通过 Project OS preflight 后，签发了唯一一次 DELL `value_capture` fixed-Pack Chat authority。第一步 DeepSeek 正确并行调用 reviewed Evidence 与 NumericFact reader，本地生成两份 receipt。第二步没有提交 Judgment：Provider 返回 HTTP 200、完整 JSON、`finish_reason=length`，但 16000 个 completion token 全部记为 reasoning token，最终可见文本和 tool call 都为零。Runtime 因此以 `model_gateway_reasoning_budget_exhausted` 终止，0 retry、0 fallback。

这意味着本轮不能评价 L1 或研报内容，也不能说 DeepSeek 不遵循最终 Judgment 合同；模型根本没有形成可验证提交。

## 大白话根因

我们给模型看的东西仍然太像“审计数据库导出”，不像一份可执行研究工作台：

1. ClaimAuthority、ClaimRelation、RoleMethodPack 和 GraphContextPack 在初始消息里出现一次，Evidence 工具返回后又出现一次；
2. NumericFact 把 source digest、observation ID、fact request ID、citation URL、accepted_at 等本地审计 lineage 全部发给模型，虽然模型只需要 ref、指标、数值、单位、期间、事实类型和必要公式；
3. 本轮 EvidenceRequest 预算明确是 0，但仍发送了约 4.3k 字符的 EvidenceRequest tool schema；
4. 每个 narrative atom 要重复填写 subject、outcome、relation、attribution、claim scope、financial scope 和 bridge authority 七个字段，而这些字段实际上已经被本地 allowed combination 冻结，可以由模型选一个 alias、本地确定性展开。

第二步最终包含约 52.4k 字符 messages 和 11.1k 字符 tools，prompt 为 18,902 token。这个负担与 `thinking=max` 共同触发了 16k reasoning budget 耗尽。

## 结构性 successor

不提高字符上限、不切换模型、不自动重跑。下一包一次完成：

- 模型只为三个 atom 选择 `ClaimRelationAlias`，Harness 展开完整七字段关系并继续做现有证据／关系／叙事冲突校验；
- Claim／Method／Graph 卡只在 mandatory read 后出现一次；初始消息只保留任务、边界和 alias 说明；
- 建立紧凑的 model-visible NumericFact／NumericRelation／QF view，完整 lineage 继续留在内部对象与 raw capture；
- EvidenceRequest budget 为 0 时，wire tool surface 不再包含该工具；
- 用本轮 immutable request/capture 做零网络 replay，比较 message/tool 字符量、合同闭合、旧 full-field payload 拒绝、alias 展开、跨案例污染和 raw lineage 留存；
- 只有 clean proof 通过后，才另行签发一个新 attempt；R1 永不改写。

## 边界

本轮不是模型质量通过或失败结论，不是动态 Agentic Research，不授权五单元。它暴露的是 fixed-Pack Harness 的模型视图仍然过密；这属于 S3 当前合同责任，应在第一项内闭合。
