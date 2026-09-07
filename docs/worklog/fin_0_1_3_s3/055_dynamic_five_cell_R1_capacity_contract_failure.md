# 055 DELL 动态五单元 R1 容量合同失败

日期：2026-08-17

## 发生了什么

R1 的 DeepSeek Planner 正常完成：提出 10 条研究原子，Harness 按既定预算选择 8 条、延期 2 条。当前 S1/S2 随后执行 8 条检索 lane，取得 128 个 hybrid 候选、24 个去重叙事候选，并处理 30 个 typed fact request，其中 22 resolved、8 gap、0 conflict；未审候选 0 晋升，外部网络 0。

链路在任何五单元分析调用前停止。`value_capture` 得到 4 条 Evidence 和 10 条 NumericFact；Evidence 未超 8，但 NumericFact 超过 consumer policy v1.3 的静态上限 8，因此终态为 `research_consumer_cell_capacity_exceeded`。本轮只发生 1 次付费模型调用，五个 Judgment 和综合均未开始。

## 为什么这不是简单调大数字

当前 route policy 明确允许 `pricing_and_value_capture` 使用五个指标：收入、毛利、毛利率、营业利润、营业利润率。同期选择器又为每个指标保留当期和上年同期，完整原子组天然是 `5 × 2 = 10`。因此 v1.3 的 8 与上游合同本身冲突；这不是 DeepSeek 多写两个字段，也不是随机碰到的长度越界。

正式零调用预回放只出现 8 条 value_capture NumericFact，漏掉了 `reported_results + margin_and_incremental_profit` 两条合法 sibling 同时出现的 mutation。这是 proof coverage 不足，应在当前 S3 consumer 门修复，不能记成模型失败。

## 有界后继

1. R1 authority、公开终态、私有 full result 与所有 capture 保持不可变。
2. consumer policy 使用新版本；旧 v1.3 不修改。
3. 新合同要么从路线原子组推导容量，要么明确绑定五指标同期对，完整 10 条通过、缺一/重排稳定、额外第 11 条拒绝。
4. 直接重放 R1 的 immutable planner 和 controlled plan，先编译五个单元、消息和 Tool Schema；不调用模型、不重跑 S1/S2。
5. 零调用 successor 通过后，仍使用同一稳定 runner，但以新的 successor authority 复用 Planner/S1/S2，只授权剩余 12 个模型节点。
6. 如果后续出现内容 L1 或质量问题，再按其最早责任层处理；不把本次容量失败和模型内容混为一谈。
