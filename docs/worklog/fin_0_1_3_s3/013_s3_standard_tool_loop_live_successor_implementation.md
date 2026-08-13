# S3 标准 Tool Calls live successor 实现

日期：2026-08-14
状态：`working_tree_engineering_pass / clean_zero_call_successor_pending / model_calls_zero`

## 为什么插入这一步

paired R2 的 JSON control 证明了非工具最终提交，但 DELL 五单元依赖标准 API 多轮 Tool Calls；strict Beta 又只留下无 HTTP 响应的传输故障。直接从 JSON 跳到五单元会把未经真实验证的多轮 continuation、工具结果和 terminal 物化一次放大到最多 24 次调用。

## 本轮实现

- standard GA profile v1.1 使用 16,000-token 上限，避免复现 R1 的 5,000 reasoning exhaustion；
- provider-neutral policy 可按本次 cell 数收窄；DELL `value_capture` 单 cell 最多 6 step；
- 每 cell 必须先读取 reviewed Evidence 与 NumericFact，不能直接交 Judgment 伪装工具研究；
- execution budget 对模型可见，EvidenceRequest 仍只记录 proposal；
- 成功 step 立即保存 receipt，中途失败保留成功前缀、phase/code、capture ref 与实际调用数；
- 复用现有唯一 canary runner，未新增 attempt runner；五 cell 将来必须引用新的显式授权决策。

## 工程证明与边界

全仓 259 tests；活动图 115 Python／8 frontend／10 Runtime resources，0 forbidden reference；secret scan 6,497 files／0 finding。fake success 路为 Evidence read → NumericFact read → Judgment；第二步 transport failure 保留第一步 receipt 且 0 retry。当前 0 模型／Provider／网络调用，不是 clean proof、真实 transport pass、内容验收、五单元或 S3 acceptance。下一门是干净提交后的 fresh zero-call successor。
