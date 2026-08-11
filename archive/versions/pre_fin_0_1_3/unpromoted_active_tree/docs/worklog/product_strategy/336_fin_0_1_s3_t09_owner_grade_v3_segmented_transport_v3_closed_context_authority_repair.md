# FIN 0.1 S3-T09 transport-v3 字段级闭合 context authority 零调用修复

日期：2026-07-22

## 授权与边界

用户在上一项根因决策后明确“授权下一步”，随后以“继续”要求执行当前项。本轮只实现 `S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V3-FIELD-LOCAL-CLOSED-CONTEXT-AUTHORITY-AND-SAFE-SUBTYPE-TELEMETRY-ZERO-CALL-IMPLEMENTATION`，范围为代码、完整生产模型视图的 fake Provider fixtures、deterministic/canonical 合同测试与 Project OS 同步。没有签发或消费 admission，没有真实模型、Provider、网络、来源、工具、Agent Run、Artifact、paired comparison 或 Human Review，也没有进入 T10/S4/release/production。

## 实现结果

新增显式 transport `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v3`；历史 v1/v2 与 canonical output-v3 均不改写。Claim Card 请求现在在真实输出 schema 之外增加字段级 `field_authority_contract`：其 `allowed_context_refs` 只来自当前 Cell 的 Candidate＋Graph context authority，按原始字符串精确去重排序；`judgment_layer.context_refs` 只能复制该列表的精确子集，不使用 context 时输出 `[]`。Evidence、Numeric、fact、routing 和自由文本/派生 ref 被显式禁止，响应前要求逐值 exact-membership 自检。

本地 validator 仍是最终 authority owner，且不做 trim/coerce/drop/remap/fuzzy match/retry。v3 在完整 claim-card schema 校验前按固定优先级区分：非字符串或空白、Evidence/Numeric 被错放为 context、当前 Cell 闭合集合之外的 ref。任何一类都在当前 segment earliest-stop；随后原有完整 owner-grade validator 仍会执行，因而没有弱化 cardinality、重复项、support fact 或 scope 合同。

新增 `segmented_specialist_authority` closed telemetry。canonical 只接纳固定 segment、字段、三种 subtype、正整数 failing count，以及五个明确为 false 的非持久化标志；raw ref、ref digest、item index、任意 key name 和 private reasoning 均被拒绝。该 family 与 strict-tool、segment-shape、segment-text telemetry 继续互斥。

## Fixture 真实性与验证

新 fixtures 不再 monkeypatch `_specialist_model_view` 为两个字段，而是使用生产代码生成包含 decision/specialist authority、Evidence、Numeric、Graph 和 authority refs 的完整模型视图。fake Provider 不回放预先写死的合法 context ref，而是从每次请求的 `field_authority_contract.allowed_context_refs` 推导输出。

正例分别证明 exact subset 与 `[]` 均可完成 12 次 fake call、六个逻辑节点和九类 Artifact。五个负例覆盖非字符串、空白、Evidence ref、Numeric ref 和任意越权 ref，全部在 Demand Claim Card 的第 2 次 fake call 后停止；failure observation 只含 subtype/count，注入的越权字符串未被持久化。历史 v2 请求仍没有 v3 字段合同，原 `context_refs` schema 文案保持不变。

验证结果：首次 implementation-specific `8 passed`；canonical failure path `14 passed`；完整 S3-T09 `172 passed in 263.75s`；加入 durable result/backlog freeze 后最终专项为 `9 passed`；Python compile、JSON parse 与 `git diff --check` 通过。workspace Python 未安装 Ruff，已如实记录为 not available，而非伪装成 lint pass。

## 产品判断与下一项

本轮产品能力增量是：项目现在能把 claim `context_refs` 的合法选择空间收紧为字段旁的精确闭合集合，并在不泄露内容的前提下区分三类 authority failure。研究质量增量仍为 0：没有新 Evidence、Numeric、Judgment、Report、Alpha 或完整 live Artifact，不能据此把 Agent 认定为 junior analyst 产品。

RC-P36-039 推进为 `transport_v3_zero_call_fixture_proven_fresh_agent_proof_decision_pending_separate_authority`；RC-P36-037、T09、T10、S4、release、production 继续 blocked。当前唯一下一项是 `S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V3-FRESH-AGENT-PROOF-DECISION`，仍需单独授权；它只能零调用冻结 fresh identity/input/budget/nonreuse/stop 合同，不能签发或执行。即使未来另行授权一次 live proof，同类 authority failure 再现也必须转 provider-route disposition，不能继续第四轮 prompt-only 修补。
