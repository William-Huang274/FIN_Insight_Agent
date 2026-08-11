# Model Run: 20260601_fin_agent_s5_specialist_layer_gate_after_s4_v0_1

## Summary
- Purpose: Run S5 Specialist layer from passed S1-S4 artifacts without rerunning retrieval.
- Status: accepted for S5 layered quality gate.
- Run type: inference evaluation.
- Timestamp: 2026-06-01 UTC.
- Environment: local Windows workstation, DeepSeek API via environment variable only.

## Code And Command
- Entry point: `scripts/eval_multi_agent_specialist_layer_gate.py`.
- Command: `python scripts\eval_multi_agent_specialist_layer_gate.py --activation-summary eval\sec_cases\outputs\multi_agent_activation_diagnostic\20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1\activation_diagnostic.json --relationship-summary eval\sec_cases\outputs\multi_agent_universe_relationship_diagnostic\20260601_fin_agent_s2_relationship_inference_onepass_deepseek_v0_3\universe_relationship_diagnostic.json --evidence-summary eval\sec_cases\outputs\multi_agent_evidence_operator_diagnostic\20260601_fin_agent_s3_after_s2_onepass_and_8k_routefix_v0_1\evidence_operator_diagnostic.json --coverage-summary eval\sec_cases\outputs\multi_agent_coverage_reflection_diagnostic\20260601_fin_agent_s4_after_8k_second_pass_routefix_v0_1\coverage_reflection_diagnostic.json --run-id 20260601_fin_agent_s5_specialist_layer_gate_after_s4_v0_1 --max-tokens 2200 --max-repair-attempts 1 --strict`.
- Raw model responses: not saved.

## Inputs
- S1: `20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1`.
- S2: `20260601_fin_agent_s2_relationship_inference_onepass_deepseek_v0_3`.
- S3: `20260601_fin_agent_s3_after_s2_onepass_and_8k_routefix_v0_1`.
- S4: `20260601_fin_agent_s4_after_8k_second_pass_routefix_v0_1`.

## Results
- Gate: pass.
- Specialist cases: `2/2`.
- Specialist routes: `7`.
- Real-evidence quality pass: `2/2`.
- Repair attempts: `0`.
- Tokens: input `56,331`, output `8,920`, total `65,251`.
- `ma_ai_capex_supply_chain_deep`: Industry Specialist saw `32` industry/relationship rows, relationship summary `24` rows, and cited `14` relationship refs.

## Decision
- Proceed to S6 Judgment Aggregator.
- S5 cost remains high and should stay visible in S6/S7 optimization; this run proves Specialist evidence conversion, not final memo quality.
