# Model Run: 20260601_fin_agent_s2_universe_relationship_quality_gate_deepseek_v0_3

## Summary

- Purpose: validate S2 Universe / Relationship under the new layered quality framework, reusing the passed S1 Research Lead artifact.
- Status: superseded by `20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_2`.
- Run type: inference evaluation.
- Timestamp: 2026-06-01.
- Environment: local Windows workspace, real DeepSeek `deepseek-v4-pro`.
- Safety: runtime credential was used only through the process environment. Plaintext credential and raw LLM responses were not saved.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent_universe_relationship_gate.py`
  - `scripts/audit_fin_agent_layer_quality.py`
- Changed surfaces:
  - `scripts/eval_multi_agent_universe_relationship_gate.py`
  - `scripts/audit_fin_agent_layer_quality.py`
  - `src/sec_agent/relationship_graph.py`
  - `tests/test_fin_agent_layer_quality_audit.py`
- Command shape:

```text
<set DeepSeek credential in process env>
python scripts/eval_multi_agent_universe_relationship_gate.py --activation-summary eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1/activation_diagnostic.json --run-id 20260601_fin_agent_s2_universe_relationship_quality_gate_deepseek_v0_3 --strict

python scripts/audit_fin_agent_layer_quality.py --summary eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_universe_relationship_quality_gate_deepseek_v0_3/universe_relationship_diagnostic.json --strict
```

## Inputs

- Upstream artifact: S1 activation diagnostic `20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1`.
- S2 case count: `1`, only the S1 case that activated `universe_relationship`.
- User prompt: AI capex supply-chain / upstream-downstream transmission for NVDA, AMD, MSFT, AMZN, GOOGL.
- Candidate boundary:
  - Bounded relationship lookup from `configs/sector_depth_packs_v0_2.yaml`.
  - No SEC retrieval, market retrieval, industry retrieval, Specialist, Memo Writer, or full-chain execution.

## Debug Sequence

| Run | Status | Finding | Action |
| --- | --- | --- | --- |
| `v0_1` | fail | Lookup returned `24` relationship rows, but Universe plan had `0` relationships. | Found S2 runner only passed S1 search-scope tickers into source inventory, so route compaction filtered bounded related tickers out. |
| `v0_2` | pass but not accepted as final | Plan emitted `8` relationships, but AI capex query mixed in energy pack rows such as OXY/HAL/LNG/WMB. | Tightened relationship pack selection: removed generic `capex` from AI aliases and required explicit AI + power/load + transmission signal for cross-sector pack merging. |
| `v0_3` | pass | Relationship lookup and plan both use AI infrastructure pack only. | Accepted as an interim relationship-list gate, later superseded by the EconomicLinkMap S2 gate. |

## Results

| Metric | Value |
| --- | ---: |
| Gate status | pass |
| Case count | 1 |
| Pass count | 1 |
| Total latency | 185,999 ms |
| Total tokens | 5,845 |
| Fallback count | 0 |
| Lookup relationship count | 24 |
| Plan relationship count | 8 |

Final plan relationship refs are all from `technology_ai_infrastructure_depth`:

- `sector_depth_pack:technology_ai_infrastructure_depth:DELL`
- `sector_depth_pack:technology_ai_infrastructure_depth:HPE`
- `sector_depth_pack:technology_ai_infrastructure_depth:SMCI`
- `sector_depth_pack:technology_ai_infrastructure_depth:ANET`
- `sector_depth_pack:technology_ai_infrastructure_depth:MRVL`
- `sector_depth_pack:technology_ai_infrastructure_depth:LRCX`
- `sector_depth_pack:technology_ai_infrastructure_depth:KLAC`
- `sector_depth_pack:technology_ai_infrastructure_depth:SNPS`

New layered quality audit:

| Metric | Value |
| --- | ---: |
| Audit schema | `fin_agent_layer_quality_audit_v0.1` |
| Source type | `universe_relationship` |
| Gate status | pass |
| Weighted score | 2.736 |
| Quality flags | none |

As with S1, the weighted score is stage-only diagnostic and not a full deliverable memo score.

## Decision

- Do not use this run as the current S2 artifact. Use `20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_2`, which adds bounded entities, economic links, mechanisms, and investment implications.
- Proceed to S3 Evidence Operators using S1 activation and the EconomicLinkMap S2 relationship artifact.
- Do not run Specialist or full-chain until S3/S4 pass.

## Outputs

- S2 summary: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_universe_relationship_quality_gate_deepseek_v0_3/universe_relationship_diagnostic.json`
- S2 audit JSON: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_universe_relationship_quality_gate_deepseek_v0_3/fin_agent_layer_quality_audit.json`
- S2 audit Markdown: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_universe_relationship_quality_gate_deepseek_v0_3/fin_agent_layer_quality_audit.md`

## Verification

```text
python -m pytest tests/test_fin_agent_layer_quality_audit.py tests/test_multi_agent_universe_relationship_llm.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_real_llm_chain_eval.py -q
result: 26 passed

python -m compileall src/sec_agent/relationship_graph.py scripts/audit_fin_agent_layer_quality.py scripts/eval_multi_agent_universe_relationship_gate.py
result: pass

git diff --check -- <S2 touched files>
result: pass
```

## Caveats And Next Step

- Not run: S3 retrieval, S4 coverage, Specialists, Memo Writer, Verifier, Renderer, full-chain.
- Relationship rows remain sector-depth hypotheses, not confirmed commercial customer/supplier facts.
- Next decision: run S3 Evidence Operators with real retrieval using the passed S1/S2 artifacts.
