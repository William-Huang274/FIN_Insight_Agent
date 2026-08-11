# 206 Multi-agent Real LLM Layered Chain Eval

日期：2026-05-30

## Prompt

用户要求基于 185/186 新增的 multi-agent 功能和架构，设计不同考察层次的测试用例与 eval 标准，并用真实 DeepSeek API 先跑 1-2 个详细链路用例，再扩展到单轮、多轮 full chain 稳定性测试。

## Decision

本轮把评测对象从 Step16 的小型 graph smoke 扩展为分层链路 eval，而不是只看最终 rendered answer。

评测层次固定为：

- Research Lead：真实 LLM 是否被调用、activation plan 是否过 validator、execution mode 是否匹配、是否错误激活禁止 agent、是否把直接工具调用留给 operator。
- Universe / Relationship：需要 relationship route 时是否调用 `relationship_graph_lookup`，UniverseRelationshipPlan 是否过 validator，relationship claim 是否只作为 scope / hypothesis evidence。
- Evidence Operators：operator agent 与 tool name 是否匹配 registry 权限矩阵，tool budget 是否受控，重复调用和预算 loop break 是否可见。
- Specialist Analysts：Fundamental / Industry-Supply-Chain / Market-Valuation / Risk 的 route result 是否存在、是否 schema pass，unsupported specialist block 是否 bounded。
- Memo Writer / Verifier：Memo Writer 只消费 verified Judgment Plan；Verifier 只允许硬边界错误阻断，支持一轮 bounded repair；最终 claim verification 必须 pass 或进入明确 bounded fallback。
- Payload safety：summary artifact 不保存 raw evidence、API key、私有路径或 raw LLM response。

## Work Completed

- 新增真实 LLM 链路 fixture：
  - `tests/fixtures/multi_agent_real_llm_chain_cases_v0_1.jsonl`
  - 6 个用例覆盖 detailed probe、single-turn、multi-turn：
    - focused management commentary
    - deep AI capex relationship
    - exact metric lookup
    - standard peer / market memo
    - scope revision t1
    - scope revision t2
- 新增真实 LLM 链路 eval runner：
  - `scripts/eval_multi_agent_real_llm_chain.py`
  - 支持 `--case-id`、`--category`、`--limit`、`--strict`、真实 LLM profile env 和 multi-turn `conversation_id` / `turn_index`。
  - 每个 case 输出 `real_chain_case_score.json`，汇总输出 `real_chain_eval_summary.json` 与 `real_chain_case_scores.jsonl`。
- 新增 eval 单测：
  - `tests/test_multi_agent_real_llm_chain_eval.py`
  - 覆盖 fixture schema 和 synthetic layered scoring。
- 修复真实 LLM 暴露的问题：
  - `memo_llm.py`：把 bounded-block policy 注入 Verifier prompt；当 deterministic verifier 已 pass 时，只允许硬边界错误阻断，避免 LLM 因“细节不足”等软错误把安全 bounded answer 降级。
  - `langgraph_orchestrator.py`：Verifier 对注入/LLM fail 执行一轮 bounded repair 后重新验证，并把 repair round 记录到 ledger/summary。
  - multi-agent summary artifact 增加 Lead / Universe / Memo / Verifier route diagnostics、specialist route results 和 relationship graph summary。

## Verification

本轮真实 DeepSeek API key 只通过临时进程环境变量注入，未写入 `.env`、文档、报告或 raw response。

- Detailed probe：
  - run id: `codex_real_llm_chain_detailed_probe_v0_1`
  - command: `python scripts/eval_multi_agent_real_llm_chain.py --run-id codex_real_llm_chain_detailed_probe_v0_1 --case-id ma_real_probe_focused_management_commentary --case-id ma_real_probe_deep_ai_capex_relationship --strict`
  - result: `2/2 passed`
- Single + multi-turn first broad gate after repair：
  - run id: `codex_real_llm_chain_single_multi_v0_2`
  - result: `4/4 passed`
- Full 6-case final gate：
  - run id: `codex_real_llm_chain_full6_v0_3`
  - output: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/codex_real_llm_chain_full6_v0_3/real_chain_eval_summary.json`
  - result: `6/6 passed`
  - pass rate: `1.0`
  - total tool calls: `35`
  - elapsed: `594883 ms`
  - category results: detailed probe `2/2`、single-turn `2/2`、multi-turn `2/2`
- Deterministic chain eval：
  - command: `python scripts/eval_multi_agent_chain_performance.py --output-dir reports/eval/multi_agent_chain_performance/codex_v0_5 --fail-on-gate`
  - result: `7/7 passed`
- Unit / targeted regression：
  - `pytest tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_langgraph_routing.py -q`
  - result: `19 passed`
- Full regression：
  - `pytest -q`
  - result: `371 passed in 17.32s`

## Findings

- 真实 Lead LLM 能稳定把 exact lookup、focused answer、standard memo、deep research 和 multi-turn scope revision 路由到预期 execution mode。
- Universe / Relationship route 已真实接入 graph：deep relationship 用例调用 `relationship_graph_lookup`，Universe validation `pass`，relationship evidence 仍被限定为 scope/hypothesis，不作为公司财务事实。
- Specialist LLM 可以产出 schema-valid memolet，但在 dry-run / bounded evidence 场景下，specialist verification 经常正确进入 bounded block；这属于当前 evidence 约束下的安全行为，不是 full memo 质量通过。
- Verifier LLM 的软性 completeness 判断存在波动；本轮把“deterministic pass 后的软错误降级”落成 hard-boundary policy，只保留 raw/tool/unsupported/new-fact/source-boundary/market-date 等硬错误阻断。
- Multi-turn t1/t2 能继承 conversation context 并重新路由，t2 可升级到 deep relationship route，未出现 stale ticker scope。

## Safety Notes

- `raw_llm_response_saved=false`，`api_key_saved=false`。
- `eval/sec_cases/outputs/...` 和 `reports/eval/...` 是 diagnostic/generated outputs，不作为默认 tracking candidate。
- 当前真实 full-chain eval 仍是 diagnostic-only；多数 evidence operator 仍使用 bounded dry-run rows，因此不能宣称生产级投研 memo 质量。

## Next Step

- 用真实 evidence rows 替换 dry-run bounded rows，专门测试 specialist 分析质量、行业数据源和 source-family ownership。
- 把 `scripts/eval_multi_agent_real_llm_chain.py` 接入后续 release/readiness smoke，但保持 feature flags diagnostic-only。
- 扩展 multi-turn 到非连续 follow-up、artifact inspection、context compression 后的 scope revision。
