# Model Run: 20260601_fin_agent_s3_evidence_operator_gate_v0_4

## Summary

- Purpose: validate S3 Evidence Operators under the layered quality framework, reusing passed S1 Research Lead and S2 EconomicLinkMap artifacts.
- Status: accepted for S3 layered quality gate.
- Run type: retrieval/operator evaluation.
- Timestamp: 2026-06-01.
- Environment: local Windows workspace, in-process SEC retrieval plus BGE reranker.
- Safety: S3 did not call an LLM and did not use a runtime API credential.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent_evidence_operator_gate.py`
  - `scripts/audit_fin_agent_layer_quality.py`
- Changed surfaces:
  - `scripts/eval_multi_agent_evidence_operator_gate.py`
  - `scripts/audit_fin_agent_layer_quality.py`
  - `src/sec_agent/ledger_store.py`
  - `src/sec_agent/mcp_tool_registry.py`
  - `src/sec_agent/multi_agent_runtime.py`
  - `tests/test_sec_agent_ledger_store.py`
  - `tests/test_multi_agent_operator_permissions.py`
  - `tests/test_fin_agent_layer_quality_audit.py`
- Command shape:

```text
python scripts/eval_multi_agent_evidence_operator_gate.py --run-id 20260601_fin_agent_s3_evidence_operator_gate_v0_4 --strict

python scripts/audit_fin_agent_layer_quality.py --summary eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260601_fin_agent_s3_evidence_operator_gate_v0_4/evidence_operator_diagnostic.json --strict
```

## Inputs

- S1 artifact: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1/activation_diagnostic.json`
- S2 artifact: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_2/universe_relationship_diagnostic.json`
- Candidate boundary:
  - Graph entry starts at `route_by_execution_mode`.
  - Graph stops after `execute_evidence_operators`.
  - No Specialist, Coverage/Reflection second pass, Aggregator, Memo Writer, Verifier, Renderer, full-chain, or multi-turn execution.

## Debug Sequence

| Run | Status | Finding | Action |
| --- | --- | --- | --- |
| `v0_1` | fail | MSFT capex exact-value rows were `0` because the route asked for 2026 annual 10-K, while available rows were 2026 10-Q period-role variants. | Added metric-family aliases and exact-value filing/period relaxed fallback. |
| `v0_2` | pass | Targeted exact + AI relationship coverage passed. | Expanded to the default 4-case operator suite. |
| `v0_3` | fail | AMZN focused case triggered BGE rerank, but `auto` device policy selected CPU even though CUDA was available. | Fixed BGE auto/default policy to select CUDA whenever available. |
| `v0_4` | pass | All four operator cases passed. | Accepted for S3. |

## Results

| Metric | Value |
| --- | ---: |
| Gate status | pass |
| Case count | 4 |
| Pass count | 4 |
| Failed count | 0 |
| Tool calls | 14 |
| SEC context rows | 300 |
| Runtime ledger rows | 349 |
| Market snapshot rows | 7 |
| Industry snapshot rows | 10 |
| SEC candidates before rerank | 360 |
| Sent to BGE rerank | 300 |
| BGE CUDA auto gate | 4/4 |

Case coverage:

| Case | Mode | Evidence rows |
| --- | --- | --- |
| `ma_msft_capex_lookup` | deterministic lookup | ledger `37` |
| `ma_amzn_margin_focused` | focused answer | SEC context `20`, ledger `6`, BGE `cuda` |
| `ma_nvda_amd_market_standard` | standard memo | SEC context `40`, ledger `136`, market `2`, BGE `cuda` |
| `ma_ai_capex_supply_chain_deep` | deep research | SEC context `240`, ledger `170`, market `5`, industry `10`, relationship lookup `24`, relationship plan `4`, BGE `cuda` |

Layered quality audit:

| Metric | Value |
| --- | ---: |
| Audit schema | `fin_agent_layer_quality_audit_v0.1` |
| Source type | `evidence_operators` |
| Gate status | pass |
| Weighted score | 2.792 |
| Quality flags | none |

## Decision

- Accept this as the current S3 artifact.
- S3 proves real evidence retrieval and row materialization, not downstream investment reasoning.
- Proceed to S4 Coverage / Reflection by reusing the S3 tool observations and rows; do not jump to full-chain yet.

## Outputs

- S3 summary: `eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260601_fin_agent_s3_evidence_operator_gate_v0_4/evidence_operator_diagnostic.json`
- S3 audit JSON: `eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260601_fin_agent_s3_evidence_operator_gate_v0_4/fin_agent_layer_quality_audit.json`
- S3 audit Markdown: `eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260601_fin_agent_s3_evidence_operator_gate_v0_4/fin_agent_layer_quality_audit.md`

## Verification

```text
python -m pytest tests/test_sec_agent_ledger_store.py tests/test_multi_agent_operator_permissions.py tests/test_fin_agent_layer_quality_audit.py tests/test_multi_agent_universe_relationship_llm.py tests/test_relationship_graph_lookup.py -q
result: 41 passed

python -m compileall src/sec_agent/ledger_store.py src/sec_agent/mcp_tool_registry.py src/sec_agent/multi_agent_runtime.py src/sec_agent/multi_agent_contracts.py src/sec_agent/universe_relationship_llm.py scripts/eval_multi_agent_universe_relationship_gate.py scripts/eval_multi_agent_evidence_operator_gate.py scripts/audit_fin_agent_layer_quality.py
result: pass
```

## Caveats And Next Step

- `ma_amzn_margin_focused` still has an initial exact-ledger partial call before context retrieval supplies usable evidence; this is acceptable for S3 because final row payload and retrieval gates pass, but S4 should decide whether second-pass coverage needs improvement.
- S3 does not assess Specialist claim-card quality, Aggregator thesis quality, Memo Writer naturalness, or Verifier depth.
- Next layer: S4 Coverage / Reflection gate.
