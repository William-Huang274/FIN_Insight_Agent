# Model Run: 20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1

## Summary
- Purpose: Validate S5 Specialist layer after adding shared specialist context and slot-aware prompt-row compression.
- Status: accepted for S5 layered quality gate.
- Run type: inference evaluation.
- Timestamp: 2026-06-01 Asia/Shanghai.
- Environment: local Windows workstation, DeepSeek API via environment variable only.

## Code And Command
- Entry point: `scripts/eval_multi_agent_specialist_layer_gate.py`.
- Command: `python scripts\eval_multi_agent_specialist_layer_gate.py --activation-summary eval\sec_cases\outputs\multi_agent_activation_diagnostic\20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1\activation_diagnostic.json --relationship-summary eval\sec_cases\outputs\multi_agent_universe_relationship_diagnostic\20260601_fin_agent_s2_relationship_inference_onepass_deepseek_v0_3\universe_relationship_diagnostic.json --evidence-summary eval\sec_cases\outputs\multi_agent_evidence_operator_diagnostic\20260601_fin_agent_s3_after_s2_onepass_and_8k_routefix_v0_1\evidence_operator_diagnostic.json --coverage-summary eval\sec_cases\outputs\multi_agent_coverage_reflection_diagnostic\20260601_fin_agent_s4_after_8k_second_pass_routefix_v0_1\coverage_reflection_diagnostic.json --run-id 20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1 --max-tokens 2000 --max-repair-attempts 1 --strict`.
- Code version: based on commit `1df530f`; working tree included shared-context / slot-aware Specialist changes.
- Raw model responses: not saved.
- Runtime credential: read from environment variable only; not written to artifacts.

## Inputs
- S1: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1/activation_diagnostic.json`.
- S2: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_relationship_inference_onepass_deepseek_v0_3/universe_relationship_diagnostic.json`.
- S3: `eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260601_fin_agent_s3_after_s2_onepass_and_8k_routefix_v0_1/evidence_operator_diagnostic.json`.
- S4: `eval/sec_cases/outputs/multi_agent_coverage_reflection_diagnostic/20260601_fin_agent_s4_after_8k_second_pass_routefix_v0_1/coverage_reflection_diagnostic.json`.

## Outputs
- Summary: `eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1/specialist_layer_diagnostic.json`.
- Case artifacts:
  - `eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1/ma_nvda_amd_market_standard/`.
  - `eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1/ma_ai_capex_supply_chain_deep/`.

## Results
- Gate: pass.
- Specialist cases: `2/2`.
- Specialist routes: `7`.
- Real-evidence quality pass: `2/2`.
- Repair attempts: `0`.
- Tokens: input `44,778`, output `8,183`, total `52,961`.
- Baseline comparison: previous S5 `20260601_fin_agent_s5_specialist_layer_gate_after_s4_v0_1` used `65,251` total tokens, so this run reduced total tokens by `12,290` (`18.8%`) while preserving gate status.

## Case Metrics

| Case | Status | Tokens | Prompt-visible row counts |
| --- | --- | ---: | --- |
| `ma_nvda_amd_market_standard` | pass | `17,836` | Fundamental `12`, Market `2`, Risk `8` |
| `ma_ai_capex_supply_chain_deep` | pass | `35,125` | Fundamental `16`, Industry `18` + relationship summary `8`, Market `5`, Risk `16` |

## Interpretation
- The run validates prompt-level compression, not upstream data truncation. Upstream data views still contain wider rows, while Specialist prompts receive slot-ranked visible rows.
- Industry relationship evidence remained valid: `technology_ai_infrastructure_depth` relationship refs were available and cited.
- No repair attempts were needed, indicating the compact shared-context prompt did not destabilize Specialist JSON output.

## Decision
- Accept this as the current S5 Specialist layer baseline.
- Proceed with downstream Aggregator / Memo Writer optimization using shared-context and selected-claim payload principles.
