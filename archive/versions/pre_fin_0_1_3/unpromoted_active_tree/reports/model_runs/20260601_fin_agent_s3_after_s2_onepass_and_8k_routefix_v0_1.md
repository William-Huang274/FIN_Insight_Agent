# Model Run: 20260601_fin_agent_s3_after_s2_onepass_and_8k_routefix_v0_1

## Summary
- Purpose: Re-run S3 Evidence Operators after S2 one-pass and 8-K route-scope fixes.
- Status: accepted for S3 layered quality gate.
- Run type: retrieval/operator evaluation.
- Timestamp: 2026-06-01 UTC.
- Environment: local Windows workstation, CUDA BGE reranker.

## Code And Command
- Entry point: `scripts/eval_multi_agent_evidence_operator_gate.py`.
- Command: `python scripts\eval_multi_agent_evidence_operator_gate.py --activation-summary eval\sec_cases\outputs\multi_agent_activation_diagnostic\20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1\activation_diagnostic.json --relationship-summary eval\sec_cases\outputs\multi_agent_universe_relationship_diagnostic\20260601_fin_agent_s2_relationship_inference_onepass_deepseek_v0_3\universe_relationship_diagnostic.json --run-id 20260601_fin_agent_s3_after_s2_onepass_and_8k_routefix_v0_1 --bge-device cuda --context-runner in_process --strict`.

## Inputs
- S1: `20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1`.
- S2: `20260601_fin_agent_s2_relationship_inference_onepass_deepseek_v0_3`.
- Retrieval indexes: sector-depth full238 mixed 10-K/10-Q/8-K BM25 and ObjectBM25.
- BGE model: local `bge-reranker-v2-m3`, device `cuda`.

## Results
- Gate: pass.
- Cases: `4/4`.
- Tool calls: `14`.
- Context rows: `371`.
- Runtime ledger rows: `399`.
- Market snapshot rows: `7`.
- Industry snapshot rows: `10`.
- SEC pre-rerank candidates: `431`.
- SEC candidates sent to BGE: `431`.
- BGE CUDA gate: `4/4`.

## Decision
- Proceed to S4/S5 using this S3 artifact.
- The earlier 8-K commentary gap is resolved upstream for the tested cases.
