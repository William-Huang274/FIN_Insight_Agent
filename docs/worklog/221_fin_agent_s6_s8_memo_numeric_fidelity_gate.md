# 221 - S6/S7/S8 Judgment / Memo / Verifier Gate 与数字一致性修复

日期：2026-06-01

## 背景

在 S5 Specialist shared-context / slot-aware compression 通过后，继续推进下游 S6 Aggregator、S7 Memo Writer、S8 Verifier 分层门控。目标是复用已通过的 S5 Specialist artifacts，不重跑 retrieval / Specialist，只验证：

- S6 是否能从 Specialist ClaimCards 聚合出可写的 `verified_judgment_plan`、`memo_thesis_plan` 和 `memo_thesis_pack`。
- S7 是否能基于 compact judgment / thesis pack 写出 claim-led memo，而不是 evidence dump 或空泛 summary。
- S8 是否能挡住 raw rows、tool calls、unsupported claims 和数字漂移。

## 主要修复

1. 新增 `scripts/eval_multi_agent_judgment_memo_gate.py`。
   - 从已通过的 S5 summary artifact 读取 specialist outputs。
   - 在 runner 内显式计算 S6 Aggregator judgment，避免 graph 从 `aggregate_judgment_plan` 进入后触发 quality second-pass 并覆盖 S5 产物。
   - graph 只从 `memo_writer` 跑到 `verifier`，用于隔离 S7/S8。
   - gate 区分 S5 route pass、S6 supported claims、thesis pack ready、Memo Writer LLM pass、fallback、claim count、raw/tool boundary 和 Verifier pass。

2. Memo Writer 增加 shared memo context。
   - 新增 `sec_agent_shared_memo_context_v0.1`，只用于 scope、coverage、route status 和 source-boundary framing。
   - Memo prompt 只允许消费 `shared_memo_context`、compact `verified_judgment_plan`、`specialist_verification`。
   - 将 output contract 调整为 thesis-led ClaimCard 写作，要求 `memo_generation_policy=thesis_led_claim_cards_v0_1`。

3. 修复 S7 内部 policy / plan 归一化。
   - 对 LLM 输出的 `memo_generation_policy` 做路由器侧归一化，避免模型漏写内部标记导致无谓 repair/fallback。
   - 输出 `memo_thesis_plan` 只保留 compact fields，避免模型复制完整 plan / thesis pack。
   - ready thesis pack 且 ClaimCards 足够时，要求 3-5 条 `memo_claims`，避免只输出一条综合 claim。

4. 增加数字一致性 gate。
   - Verifier 对 `memo_claims` 按 `claim_id` 对照上游 supported ClaimCard，拦截未出现在源 ClaimCard scope 中的重大数字 token。
   - direct answer 的重大数字漂移从 warning 升为 hard error；`3M` 等时间窗口缩写保留为 warning。
   - 对轻微四舍五入设置容忍，例如 `155.3% -> 155%` 不当作重大漂移；`22.1x -> 2.8x`、`20.7x -> 2.2x` 会被挡住。
   - Memo Writer normalize 阶段可用已验证 `memo_claims` 重写 direct answer，避免一个 direct-answer 数字错误拖垮整次写作。

5. 更新 Memo Writer skill v0.2。
   - 明确输入字段、thesis pack 优先级、3-5 claims、数字值不得重算/发明/改单位、缺证处理和禁止输出完整 pack/outline。

## 真实 DeepSeek 分层验证

最终接受 run：

- Run ID：`20260601_fin_agent_s6_s8_numeric_direct_normalized_memo_gate_deepseek_v0_7`
- 输入：`20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1`
- Cases：`2/2`
- Gate：`pass`
- Memo Writer route pass：`2/2`
- Verifier pass：`2/2`
- Fallback：`0`
- Memo repair attempts：`1`
- Token：Memo Writer `23,429`，Verifier `8,024`，Total `31,453`

Case 结果：

- `ma_ai_capex_supply_chain_deep`：one-pass；5 条 memo claims；无 Verifier warning；覆盖 AMD capex、relationship graph hypothesis、market valuation、MSFT cloud monetization counterevidence 和 source gaps。
- `ma_nvda_amd_market_standard`：1 次 repair；4 条 memo claims；保留 AMD `22.1x` / NVDA `20.7x` source-boundary，不再出现 `2.8x` / `2.2x` 漂移；残留 soft warning 为 direct answer 中 `3M` 时间窗口缩写。

调试 lineage：

- v0.1：runner 从 graph aggregate 入口触发 second-pass，覆盖 S5 outputs，导致 judgment blocked / 0 claims。
- v0.2：S6 聚合修复，但 Memo Writer policy 漏写导致 NVDA/AMD fallback。
- v0.3：2/2 pass、0 fallback，但发现 `22.1x -> 2.8x` 数字漂移。
- v0.4-v0.5：数字 gate 生效，但过严导致过度 repair / claim 压缩。
- v0.6：direct answer 数字漂移改 hard gate 后暴露 `21.8%` repair/fallback 问题。
- v0.7：direct answer numeric normalization 后通过，成本和质量达到当前可接受平衡。

## 本地验证

- `python -m compileall src/sec_agent/memo_llm.py src/sec_agent/multi_agent_contracts.py scripts/eval_multi_agent_judgment_memo_gate.py`
- `python -m pytest tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_contracts.py -q`
  - `44 passed`
- 真实 DeepSeek run：`20260601_fin_agent_s6_s8_numeric_direct_normalized_memo_gate_deepseek_v0_7`

## 结论

S6/S7/S8 可以作为当前下游分层 gate 继续使用。与之前 full-chain memo 相比，本轮输出不再只是 bounded summary：AI capex case 已能形成 thesis、drivers、counterevidence 和 source boundary；NVDA/AMD case 能在 NVDA primary filing 缺失时给出有边界的 AMD-led comparison。

## 后续

- 将 `3M` / `3-month` / `3M return` 这类时间窗口 token 做规范化，降低 Verifier soft warning 噪声。
- 将 direct-answer numeric normalization 的触发计数纳入 model-run metrics，便于观察模型是否仍频繁改数。
- 继续推进 S9 full-chain 多 case：从 S1 到 S8 串起来验证 shared context、S6/S7/S8 gate 在非 artifact-reuse 模式下的稳定性。
