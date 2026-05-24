# Worklog: SEC Benchmark v2 Next Reviewed Batch Design

Date: 2026-05-19

## Prompt

User asked to start designing the next batch of v2 reviewed cases after the
v2 plus3 metric-source grounded closeout.

## Current State

- Current v2 accepted run: `test_cases_v2_pilot_plus3_seed.jsonl`.
- Current v2 size: 9 total cases, 8 non-trap reviewed cases, 1 trap case.
- Latest pipeline result:
  `reports/quality/local_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_5090_metric_source_grounded_post_gates/sec_benchmark_post_gates_summary.json`.
- Latest status: BGE-M3 pipeline-context plus Judgment Plan plus Qwen9B passes
  all active post-gates, including metric-source grounding.

## Decision

The next batch should be an MVP-extension reviewed batch, not a full v2
benchmark. The design target is 6 candidates:

- 4 non-trap cases with existing reviewed context/fact reuse or clean splits.
- 1 text-heavy risk/not-found case.
- 1 source-policy/metric-scope trap.

This keeps the batch small enough to review and gate properly while covering
MVP gaps that plus3 does not yet stress enough.

## Design Artifact

Created:

- `docs/eval/sec_benchmark_v2_next_reviewed_batch_design.md`

Primary candidates:

- `AMZN_AWS_NUMERIC_2023_2025_001`
- `AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001`
- `MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001`
- `NVDA_DATACENTER_2023_2025_001`
- `SNOW_RISK_2023_2025_001`
- `MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001`

Key decision:

- Do not promote the broad 3-company
  `CLOUD_PROFITABILITY_2023_2025_DIAG_001` as-is. Split it into a clean
  AMZN/GOOGL comparable peer case and a separate Microsoft proxy/disclosure
  boundary case.

## Evidence Used

Existing reviewed artifacts checked:

- `eval/sec_cases/reviewed_gold_facts/AMZN_AWS_NUMERIC_2023_2025_001.json`
  has 6 reviewed AWS revenue / operating-income facts.
- `eval/sec_cases/reviewed_gold_facts/CLOUD_PROFITABILITY_2023_2025_DIAG_001.json`
  has reviewed AMZN, GOOGL, and MSFT cloud/proxy rows that can be split.
- `eval/sec_cases/reviewed_gold_context/MSFT_AI_CLOUD_2023_2025_001.jsonl`
  has 11 reviewed MSFT AI/cloud text rows.
- `eval/sec_cases/reviewed_gold_context/NVDA_DATACENTER_2023_2025_001.jsonl`
  has 12 reviewed NVDA data-center/risk text rows.
- `eval/sec_cases/reviewed_gold_context/SNOW_RISK_2023_2025_001.jsonl`
  has 9 reviewed Snowflake consumption-model risk rows.

## Follow-Up

Next concrete build order:

1. Promote `AMZN_AWS_NUMERIC_2023_2025_001` first with v2
   `required_caveats` and `disallowed_claims`.
2. Build the AMZN/GOOGL cloud profitability peer case from the reviewed cloud
   profitability subset.
3. Build the Microsoft cloud/AI margin proxy case.
4. Add NVDA and SNOW text-heavy cases with v2 caveat/claim fields.
5. Add the Microsoft Azure gross-margin not-found trap.
6. Run readiness, reviewed-gold, trap-smoke, ledger, and unit gates before any
   pipeline-context Qwen run.

## Safety Notes

- No model inference was run.
- No benchmark scores were claimed.
- No secrets or cloud credentials were written.
- The design keeps BGE-M3 as the fixed final selector for future pipeline
  runs; BM25/ObjectBM25 remain candidate generators only.
