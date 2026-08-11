# Model Run: 20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_2

## Summary

- Purpose: deepen S2 Universe / Relationship into a bounded economic-link map before downstream evidence operators or Specialists consume relationship context.
- Status: accepted for S2 layered quality gate.
- Run type: inference evaluation.
- Timestamp: 2026-06-01.
- Environment: local Windows workspace, real DeepSeek `deepseek-v4-pro`.
- Safety: runtime credential was used only through the process environment. Plaintext credential and raw LLM responses were not saved.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent_universe_relationship_gate.py`
  - `scripts/audit_fin_agent_layer_quality.py`
- Changed surfaces:
  - `src/sec_agent/multi_agent_contracts.py`
  - `src/sec_agent/universe_relationship_llm.py`
  - `src/sec_agent/relationship_graph.py`
  - `scripts/eval_multi_agent_universe_relationship_gate.py`
  - `scripts/audit_fin_agent_layer_quality.py`
  - `tests/test_multi_agent_universe_relationship_llm.py`
  - `tests/test_fin_agent_layer_quality_audit.py`
- Command shape:

```text
<set DeepSeek credential in process env>
python scripts/eval_multi_agent_universe_relationship_gate.py --activation-summary eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1/activation_diagnostic.json --run-id 20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_2 --input-max-relationships 4 --strict

python scripts/audit_fin_agent_layer_quality.py --summary eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_2/universe_relationship_diagnostic.json --strict
```

## Inputs

- Upstream artifact: S1 activation diagnostic `20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1`.
- S2 case count: `1`, only the S1 case that activated `universe_relationship`.
- User prompt: AI capex supply-chain / upstream-downstream transmission for NVDA, AMD, MSFT, AMZN, GOOGL.
- Candidate boundary:
  - Bounded relationship lookup from `configs/sector_depth_packs_v0_2.yaml`.
  - No SEC retrieval, market retrieval, industry retrieval, Specialist, Memo Writer, or full-chain execution.

## Results

| Metric | Value |
| --- | ---: |
| Gate status | pass |
| Case count | 1 |
| Pass count | 1 |
| Total latency | 72,279 ms |
| Total tokens | 11,465 |
| Fallback count | 0 |
| Lookup relationship count | 24 |
| Plan relationship count | 4 |
| Economic entity count | 6 |
| Economic link count | 4 |
| Mechanism count | 2 |
| Investment implication count | 2 |

Layered quality audit:

| Metric | Value |
| --- | ---: |
| Audit schema | `fin_agent_layer_quality_audit_v0.1` |
| Source type | `universe_relationship` |
| Gate status | pass |
| Weighted score | 2.736 |
| Quality flags | none |

## Decision

- Accept this as the current S2 artifact.
- Supersede `20260601_fin_agent_s2_universe_relationship_quality_gate_deepseek_v0_3` because that run produced a relationship list but not a structured economic transmission map.
- Proceed to S3 Evidence Operators only by reusing the accepted S1 and S2 artifacts.

## Outputs

- S2 summary: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_2/universe_relationship_diagnostic.json`
- S2 audit JSON: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_2/fin_agent_layer_quality_audit.json`
- S2 audit Markdown: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_2/fin_agent_layer_quality_audit.md`

## Caveats And Next Step

- The economic map is still relationship-hypothesis evidence, not confirmed commercial supplier/customer evidence.
- It can support research scope, transmission hypotheses, Specialist task context, and memo caveats, but not standalone financial fact claims.
- Next layer: S3 Evidence Operators with real retrieval.
