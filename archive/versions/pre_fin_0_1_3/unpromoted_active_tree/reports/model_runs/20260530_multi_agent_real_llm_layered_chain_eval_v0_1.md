# Model Run: 20260530_multi_agent_real_llm_layered_chain_eval_v0_1

## Summary

- Purpose: 真实 DeepSeek API 下评测 multi-agent 链路的 per-agent 调用、路由、工具权限、Universe relationship、Specialist、Memo Writer / Verifier 和 multi-turn 稳定性。
- Status: accepted for diagnostic Step 17 eval gate.
- Run type: inference evaluation.
- Timestamp: 2026-05-30.
- Environment: local Windows workspace, temporary process env credential injection only.
- Model: `deepseek-v4-pro` through DeepSeek OpenAI-compatible chat completions API.

## Code And Command

- Entry point: `scripts/eval_multi_agent_real_llm_chain.py`
- Fixture: `tests/fixtures/multi_agent_real_llm_chain_cases_v0_1.jsonl`
- Final command: `python scripts/eval_multi_agent_real_llm_chain.py --run-id codex_real_llm_chain_full6_v0_3 --strict`
- Feature flags:
  - `SEC_AGENT_MULTI_AGENT_LEAD_ROUTER=llm`
  - `SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER=llm`
  - `SEC_AGENT_MULTI_AGENT_UNIVERSE_ROUTER=llm`
  - `SEC_AGENT_MULTI_AGENT_MEMO_ROUTER=llm`
  - `RESEARCH_LEAD_REQUIRE_EVIDENCE_REQUIREMENTS=1`
- Git state: dirty feature branch `codex/api-model-call-architecture`; this run includes current uncommitted multi-agent implementation and docs.
- Raw LLM response: not saved.
- API key: supplied only through environment variable, not persisted.

## Inputs

- Case count: `6`
- Categories:
  - detailed probe: `2`
  - single-turn: `2`
  - multi-turn: `2`
- Case ids:
  - `ma_real_probe_focused_management_commentary`
  - `ma_real_probe_deep_ai_capex_relationship`
  - `ma_real_single_exact_metric_lookup`
  - `ma_real_single_standard_peer_market_memo`
  - `ma_real_multiturn_scope_revision_t1`
  - `ma_real_multiturn_scope_revision_t2`
- Candidate boundary: multi-agent diagnostic fixtures with bounded tool outputs; relationship graph lookup is real graph route, most evidence operator rows remain dry-run bounded rows.
- Leakage guard: no raw evidence payloads in summary artifact; no API key persistence; no private data path expected in eval summary.

## Outputs

- Final summary: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/codex_real_llm_chain_full6_v0_3/real_chain_eval_summary.json`
- Per-case scores: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/codex_real_llm_chain_full6_v0_3/real_chain_case_scores.jsonl`
- Related deterministic eval: `reports/eval/multi_agent_chain_performance/codex_v0_5`
- Worklog: `docs/worklog/206_multi_agent_real_llm_layered_chain_eval.md`

## Results

- Final full6 gate: `6/6 passed`
- Pass rate: `1.0`
- Failed cases: `[]`
- Elapsed: `594883 ms`
- Total tool calls: `35`
- Category results:
  - detailed probe: `2/2`
  - single-turn: `2/2`
  - multi-turn: `2/2`
- Deterministic chain performance eval: `7/7 passed`
- Full regression: `371 passed in 17.32s`

## Agent-Level Diagnostics

- Research Lead: `10` calls, `52395` tokens, `248691 ms`; all 6 cases had valid execution mode and no direct tool calls.
- Universe / Relationship: invoked for relationship cases; aggregate `6` calls, `62020` tokens, `141317 ms`; relationship graph lookup returned `ok` where expected.
- Specialist Analysts: `14` route attempts, `30327` tokens, `164527 ms`; route results were schema-valid and bounded when evidence was insufficient for full memo.
- Memo Writer: `1` real LLM call in the focused draft case, `3317` tokens, `12381 ms`; bounded cases correctly skipped full memo generation.
- Verifier: claim verification passed for evaluated outputs; hard-boundary verifier policy and one-round repair were validated by targeted regression tests.

## Interpretation

The run validates that the 185/186 multi-agent architecture is now wired into the diagnostic graph path: Lead routing, permissioned operator calls, Universe relationship lookup, specialist route results, Memo/Verifier gates, bounded fallback, and multi-turn scope revision are all observable in the eval summary.

This is not yet a production-quality investment memo claim. The current gate intentionally accepts bounded fallback when specialist evidence is insufficient, and most operator evidence rows are diagnostic dry-run rows. The next quality gate must use real evidence-backed specialist cases before promoting the graph beyond diagnostic-only.

## Safety Notes

- `raw_llm_response_saved=false`.
- `api_key_saved=false`.
- Do not track large generated eval output directories by default.
- Reproduce with the same run id only for audit; use a new run id for future contract changes.
