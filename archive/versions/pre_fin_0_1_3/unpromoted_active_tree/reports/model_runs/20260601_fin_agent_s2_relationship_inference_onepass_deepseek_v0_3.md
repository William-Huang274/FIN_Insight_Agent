# Model Run: 20260601_fin_agent_s2_relationship_inference_onepass_deepseek_v0_3

## Summary
- Purpose: Verify S2 Universe / Relationship can pass without repair after deterministic ticker/ref/economic-map completion.
- Status: accepted for S2 layered quality gate.
- Run type: inference evaluation.
- Timestamp: 2026-06-01 UTC.
- Environment: local Windows workstation, DeepSeek API via environment variable only.

## Code And Command
- Entry point: `scripts/eval_multi_agent_universe_relationship_gate.py`.
- Command: `python scripts\eval_multi_agent_universe_relationship_gate.py --activation-summary eval\sec_cases\outputs\multi_agent_activation_diagnostic\20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1\activation_diagnostic.json --run-id 20260601_fin_agent_s2_relationship_inference_onepass_deepseek_v0_3 --input-max-relationships 48 --max-relationships 48 --max-expanded-tickers 32 --max-tokens 2600 --max-repair-attempts 0 --strict`.
- Dirty files: source/scripts/docs touched in current iteration.
- Raw model responses: not saved.

## Inputs
- Upstream: S1 `20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1`.
- Case: `ma_ai_capex_supply_chain_deep`.
- Relationship data: sector-depth pack bounded lookup rows.

## Results
- Gate: pass.
- Cases: `1/1`.
- LLM calls: `1`.
- Repair attempts: `0`.
- Fallback count: `0`.
- Lookup relationships: `42`.
- Plan relationships: `42`.
- Deterministic completed relationships: `42`.
- Total latency: `24,333 ms`.
- Tokens: input `9,278`, output `1,697`, total `10,975`.

## Decision
- Proceed to S3/S4/S5 using this S2 artifact.
- The remaining cost is prompt payload size, not repair-loop waste.
