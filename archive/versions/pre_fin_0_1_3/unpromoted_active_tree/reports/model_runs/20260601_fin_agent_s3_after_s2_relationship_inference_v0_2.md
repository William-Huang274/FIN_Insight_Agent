# Model Run: 20260601_fin_agent_s3_after_s2_relationship_inference_v0_2

## Summary

- Purpose: rerun S3 Evidence Operators from the accepted S2 relationship-inference artifact and verify that real retrieval, rerank, exact-value ledger, market, industry, and relationship rows are all usable before Coverage / Reflection.
- Status: accepted for S3 layered quality gate.
- Run type: retrieval/operator evaluation.
- Timestamp: 2026-06-01.
- Environment: local Windows workspace, in-process SEC retrieval plus BGE reranker.
- Safety: S3 did not call an LLM and did not use a runtime API credential.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent_evidence_operator_gate.py`
  - `scripts/audit_fin_agent_layer_quality.py`
- Command shape:

```text
python scripts/eval_multi_agent_evidence_operator_gate.py --relationship-summary eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2/universe_relationship_diagnostic.json --run-id 20260601_fin_agent_s3_after_s2_relationship_inference_v0_2 --strict

python scripts/audit_fin_agent_layer_quality.py --summary eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260601_fin_agent_s3_after_s2_relationship_inference_v0_2/evidence_operator_diagnostic.json --strict
```

## Inputs

- S1 artifact: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1/activation_diagnostic.json`
- S2 artifact: `eval/sec_cases/outputs/multi_agent_universe_relationship_diagnostic/20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2/universe_relationship_diagnostic.json`
- Candidate boundary:
  - Graph starts after passed activation / relationship artifacts.
  - Graph stops after `execute_evidence_operators`.
  - No Coverage / Reflection, Specialist, Aggregator, Memo Writer, Verifier, Renderer, full-chain, or multi-turn execution.

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

Required S3 checks all passed:

- `sec_search_filings` was not dry-run.
- BM25/ObjectBM25 candidates were present before rerank.
- BGE rerank candidates were present.
- CUDA was used when `auto` was configured and CUDA was available.
- Exact-value ledger rows were present for metric cases.
- Relationship rows were available for the sector-depth case.

Layered quality audit:

| Metric | Value |
| --- | ---: |
| Audit schema | `fin_agent_layer_quality_audit_v0.1` |
| Source type | `evidence_operators` |
| Gate status | pass |
| Weighted score | 2.792 |
| Quality flags | none |

## Decision

- Accept this as the current S3 artifact for S4.
- S3 proves real retrieval and row materialization; it does not yet prove Specialist claim-card quality or memo quality.

## Outputs

- S3 summary: `eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260601_fin_agent_s3_after_s2_relationship_inference_v0_2/evidence_operator_diagnostic.json`
- S3 audit JSON: `eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260601_fin_agent_s3_after_s2_relationship_inference_v0_2/fin_agent_layer_quality_audit.json`
- S3 audit Markdown: `eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260601_fin_agent_s3_after_s2_relationship_inference_v0_2/fin_agent_layer_quality_audit.md`

## Caveats And Next Step

- Downstream nodes must consume bounded rows and source-gap summaries rather than assuming every requested source family is populated.
- Next accepted layer: S4 Coverage / Reflection.
