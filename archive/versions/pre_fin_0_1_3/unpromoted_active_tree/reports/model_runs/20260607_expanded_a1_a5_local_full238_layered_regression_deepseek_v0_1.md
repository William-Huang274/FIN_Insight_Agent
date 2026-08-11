# Model Run: 20260607_expanded_a1_a5_local_full238_layered_regression_deepseek_v0_1

## Summary

- Purpose: Run the A1-A5 layered gates after expanded-source wiring, without running expanded full-chain, and catch contract regressions before cloud expanded replay.
- Status: local full238 layered regression accepted; true expanded cloud A2-A5 blocked by SSH pre-auth disconnect.
- Run type: inference evaluation + retrieval/operator regression.
- Timestamp: 2026-06-07 Asia/Shanghai.
- Environment: local `D:\FIN_Insight_Agent`; DeepSeek API for LLM gates; local full238 BM25/ObjectBM25/BGE reranker/ledger/market/industry artifacts for S3.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent/eval_multi_agent_research_lead_activation.py`
  - `scripts/eval_multi_agent/eval_multi_agent_universe_relationship_gate.py`
  - `scripts/eval_multi_agent/eval_multi_agent_evidence_operator_gate.py`
  - `scripts/eval_multi_agent/eval_multi_agent_coverage_reflection_gate.py`
  - `scripts/eval_multi_agent/eval_multi_agent_specialist_layer_gate.py`
  - `scripts/eval_multi_agent/eval_multi_agent_judgment_memo_gate.py`
- Code change during run:
  - S3 summary now persists expanded runtime config: `milvus_top_k`, `embedding_model`, `market_snapshot_id`, `market_as_of_date`.
  - S4 `_s3_args_from_summary(...)` now restores market catalog, industry snapshot DB, and Milvus runtime fields from S3 summaries.
  - Added `tests/test_eval_multi_agent_gate_config_roundtrip.py`.
- Commands used the run IDs listed in Results; all strict gates were enabled.
- Seeds: deterministic retrieval/orchestration where applicable; LLM temperature `0`.

## Inputs

- Activation fixture: `tests/fixtures/multi_agent_activation_cases_v0_1.jsonl`.
- S3 local retrieval assets:
  - Manifest: `data/processed_private/manifests/sector_depth_full238_us_v0_2_mixed_with_8k_manifest_fy2023_2027.jsonl`
  - BM25: `data/indexes/bm25/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027`
  - ObjectBM25: `data/indexes/bm25/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects`
  - Ledger: `data/processed_private/ledger/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_core_ledger.duckdb`
- Expanded cloud assets were not used in this run because SSH closed before authentication.

## Outputs

- A1/S1 summary: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260607_expanded_a1_research_lead_cost_aware_route_gate_deepseek_v0_1/activation_diagnostic.json`
- S2 summary: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260607_expanded_s2_relationship_link_map_gate_deepseek_v0_1/universe_relationship_diagnostic.json`
- A2/S3 summary: `eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260607_expanded_a2_local_full238_evidence_operator_regression_v0_2/evidence_operator_diagnostic.json`
- A3/S4 summary: `eval/sec_cases/outputs/multi_agent_coverage_reflection_diagnostic/20260607_expanded_a3_local_full238_coverage_reflection_regression_v0_2/coverage_reflection_diagnostic.json`
- A4/S5 summary: `eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260607_expanded_a4_local_full238_specialist_source_bundle_regression_deepseek_v0_1/specialist_layer_diagnostic.json`
- A5/S6-S8 summary: `eval/sec_cases/outputs/multi_agent_judgment_memo_diagnostic/20260607_expanded_a5_local_full238_judgment_memo_verifier_regression_deepseek_v0_1/judgment_memo_diagnostic.json`

## Results

- A1/S1 Research Lead: `5/5` pass; evidence requirements `5/5`; forbidden activation `0`; tokens `27411`.
- S2 Universe / Relationship: `1/1` pass; lookup relationships `42`; plan relationships `42`; fallback `0`; tokens `10371`.
- A2/S3 Evidence Operators local full238 regression: `4/4` pass; tool calls `14`; context rows `146`; runtime ledger rows `259`; market rows `4`; industry rows `10`; SEC pre-rerank candidates `550`; BGE candidates `433`.
- A3/S4 Coverage / Reflection: `4/4` pass; second-pass allowed/ran `1`; added rows `120`; missing requirements `2`.
- A4/S5 Specialist: `2/2` pass; Specialist count `7`; real evidence quality `2/2`; tokens `51519`; repair `0`.
- A5/S6-S8 Judgment / Memo / Verifier: `2/2` pass; Memo route `2/2`; Verifier `2/2`; tokens `32221`; repair `0`.
- Targeted unit/contract tests after the fix: `20 + 46 + 36` passed.

## Interpretation

The expanded-source code wiring did not break the local full238 layered gate chain, and the S3/S4 artifact handoff now preserves the new expanded runtime fields. This is sufficient as a local regression gate and a script-readiness gate.

This is not a true expanded 603-company gate. Expanded Object SQLite FTS, expanded BM25, expanded Milvus, market catalog, industry snapshot DB, and the verified expanded ledger must still be exercised on cloud before any expanded full-chain run.

## Runtime Efficiency

- A1 wall time: about `101s`.
- S2 wall time: about `39s`.
- A2/S3 local full238 wall time: about `50s`.
- A3/S4 wall time: about `3s`.
- A4/S5 wall time: about `112s`.
- A5/S6-S8 wall time: about `60s`.
- Total recorded LLM tokens across A1/S2/S5/S6-S8: `121522`.

## Caveats And Next Step

- Cloud SSH attempts failed before authentication with remote connection closure / protocol banner errors. No cloud command was executed after the failure started, and no cloud sync happened for the script fix.
- Current S1 cost-aware output did not select `milvus_semantic`; Milvus route remains covered by operator/unit contract, not by a true full layered LLM path.
- Next step after cloud SSH recovers: sync the S3/S4 config-roundtrip fix, then run true expanded A2-A5 with explicit expanded paths before any 10-20 case expanded full-chain / multi-turn.

## Safety Notes

- No API key, SSH password, private token, or raw LLM response was saved.
- Runtime eval outputs under `eval/sec_cases/outputs/...` are generated artifacts and should not be staged by default.
