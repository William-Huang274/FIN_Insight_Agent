# Model Run: 20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2

## Summary

- Purpose: upgrade S2 Universe / Relationship so bounded sector-depth lookup rows are preserved as inferred relationship evidence instead of being dropped by the LLM output cap.
- Status: accepted for S2 layered quality gate, superseding the earlier economic-link-map-only S2 artifact for downstream S3/S4 work.
- Run type: inference evaluation.
- Timestamp: 2026-06-01.
- Environment: local Windows workspace, real DeepSeek `deepseek-v4-pro`.
- Safety: runtime credential was read from the process environment. Plaintext credential and raw LLM responses were not saved.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent_universe_relationship_gate.py`
  - `scripts/audit_fin_agent_layer_quality.py`
- Key changed surfaces:
  - `src/sec_agent/relationship_graph.py`
  - `src/sec_agent/multi_agent_contracts.py`
  - `src/sec_agent/universe_relationship_llm.py`
  - `scripts/eval_multi_agent_universe_relationship_gate.py`
  - `scripts/audit_fin_agent_layer_quality.py`
  - `tests/test_multi_agent_universe_relationship.py`
  - `tests/test_multi_agent_universe_relationship_llm.py`
  - `tests/test_relationship_graph_lookup.py`
- Command shape:

```text
<set DeepSeek credential in process env>
python scripts/eval_multi_agent_universe_relationship_gate.py --activation-summary eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1/activation_diagnostic.json --run-id 20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2 --input-max-relationships 48 --max-relationships 48 --max-expanded-tickers 32 --max-tokens 4200 --strict

python scripts/audit_fin_agent_layer_quality.py --summary eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2/universe_relationship_diagnostic.json --strict
```

## Inputs

- Upstream artifact: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1/activation_diagnostic.json`.
- Case: `ma_ai_capex_supply_chain_deep`.
- Candidate boundary:
  - Bounded relationship lookup from sector-depth pack configuration.
  - No SEC retrieval, Specialist, Aggregator, Memo Writer, Verifier, Renderer, or full-chain execution.

## Results

| Metric | Value |
| --- | ---: |
| Gate status | pass |
| Case count | 1 |
| Pass count | 1 |
| Total latency | 102,207 ms |
| Total tokens | 36,646 |
| Fallback count | 0 |
| LLM call count | 3 |
| Repair attempts | 2 |
| Lookup relationship count | 42 |
| Plan relationship count | 42 |
| Deterministically completed relationship count | 42 |
| Economic entity count | 4 |
| Economic link count | 4 |
| Mechanism count | 2 |
| Investment implication count | 2 |

Relationship inference stats:

| Field | Value |
| --- | --- |
| Inference level | `sector_inferred`: 42 |
| Confirmation status | `no_confirmed_direct_edge`: 42 |
| Direct commercial edge boundary | No explicit customer/supplier relationship graph artifact is configured; sector-depth rows remain inference-only. |

Layered quality audit:

| Metric | Value |
| --- | ---: |
| Audit schema | `fin_agent_layer_quality_audit_v0.1` |
| Source type | `universe_relationship` |
| Gate status | pass |
| Weighted score | 2.736 |
| Quality flags | none |

## Decision

- Accept this run as the current S2 artifact for downstream S3/S4 because it preserves every bounded lookup relationship row while keeping source-boundary labels explicit.
- Treat the relationship rows as research-scope and economic-transmission evidence, not confirmed customer/supplier or contract evidence.
- Keep the high token cost as a follow-up optimization item: the run passed quality gates but required two repair attempts.

## Outputs

- S2 summary: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2/universe_relationship_diagnostic.json`
- S2 audit JSON: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2/fin_agent_layer_quality_audit.json`
- S2 audit Markdown: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2/fin_agent_layer_quality_audit.md`

## Caveats And Next Step

- Existing local data supports bounded sector-depth inference, not a complete confirmed economic relationship graph.
- A confirmed direct commercial graph still needs external or newly extracted customer/supplier, contract/order, revenue exposure, or vendor/customer concentration data.
- Next accepted layer: S3 Evidence Operators using this S2 artifact.
