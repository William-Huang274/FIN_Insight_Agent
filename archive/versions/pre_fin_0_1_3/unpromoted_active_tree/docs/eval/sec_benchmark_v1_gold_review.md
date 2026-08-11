# SEC Benchmark v1 Gold Review

## Decision

The original seed Gold Context / Gold Facts are **not approved for full
mainline scored benchmark testing**.

As of 2026-05-19, a case-filtered reviewed gold subset is approved:

- 10 reviewed non-trap cases for `gold_context` scored smoke;
- 2 trap cases for refusal / unsupported-claim gate testing;
- full noisy benchmark still blocked until future added cases and full pipeline gates are separately approved.

The original seed artifacts remain approved only for:

- context-only runner smoke tests;
- pipeline refusal smoke on trap cases;
- manual review candidates for building final gold.

## Why Not Mainline Yet

The generated seed files were selected by BM25/ObjectBM25. They contain the
right evidence in several cases, but they are not clean gold.

Main blockers:

- Numeric facts include prior-period table columns and comparison rows.
- Some facts are percentage changes, percentages of total, customer counts, or
  unrelated metrics rather than the requested target values.
- Several text contexts include generic risk, audit/index, tax, revenue policy,
  or broad business rows.
- L4 diagnostic cases have too many rows to isolate model synthesis capacity.

## Current Reviewed10 Status

- Reviewed approval: `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`
- Reviewed10 gold gate: `reports/quality/sec_benchmark_v1_gold_gate_reviewed10_text_numeric_cloud_platform_table.json`
- Exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`
- Ledger unit gate: `reports/quality/sec_benchmark_v1_reviewed10_ledger_unit_gate.json`

Reviewed10 gate evidence:

- `case_count=10`
- `status_counts={"pass":10}`
- exact-value ledger `row_count=98`
- ledger unit gate `pass_count=98`, `fail_count=0`
- new metric-table case facts: 48 reviewed table cells
- new metric-table case context: 56 reviewed rows

## Original Seed Case-Level Review

| Case | Decision | Main Issue |
|---|---|---|
| `SNOW_RISK_2023_2025_001` | needs trim | Correct consumption evidence exists, but context includes unrelated risk/overview rows. |
| `NVDA_DATACENTER_2023_2025_001` | needs trim | Some data-center evidence exists, but top rows include irrelevant tax/employee/generic rows. |
| `AMZN_AWS_NUMERIC_2023_2025_001` | reject seed facts | Facts mix target AWS values with prior-period rows and non-target metrics. |
| `AAPL_AWS_TRAP_001` | approved for trap smoke | Gold Context not required; use for refusal testing. |
| `META_LLAMA_COST_TRAP_001` | approved for trap smoke | Gold Context not required; use for refusal testing. |
| `MSFT_AI_CLOUD_2023_2025_001` | needs trim | Relevant cloud/AI evidence exists, but context is broad. |
| `GOOGL_CLOUD_CONTEXT_ROLE_2025_001` | reject seed facts | Key values exist, but prior-year values are mixed into target facts. |
| `CLOUD_PROFITABILITY_2023_2025_DIAG_001` | reject seed facts | Too wide for clean Gold Context; needs compact driver/evidence pack. |
| `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001` | reject seed facts | Mixes Apple margin, Adobe ARR increases, totals, and percentage changes. |
| `REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001` | reviewed approved | Seed facts rejected, then replaced with 48 cell-level reviewed table facts and 56 compact reviewed context rows for consolidated revenue, operating income, net income, and operating cash flow. |
| `AAPL_SERVICES_MARGIN_2023_2025_001` | reject seed facts | 11/12 fact candidates are suspicious; requested Services values are not isolated. |
| `PANW_SUBSCRIPTION_VISIBILITY_2023_2025_001` | reject seed facts | Useful billings rows exist, but prior periods and irrelevant 10% rows contaminate facts. |

## Gate

Do not run the full noisy mainline scored Gold-vs-Pipeline model benchmark yet.

Allowed now:

```text
context-only runner smoke
trap pipeline refusal smoke
reviewed-gold construction
```

Required before full noisy mainline:

1. Run reviewed10 through pipeline-context true-Qwen synthesis and deterministic post-gates.
2. Add Judgment Plan / answer-plan coverage where the task requires cross-driver judgment rather than direct table extraction.
3. Expand beyond v1 with new reviewed cases before claiming generalization.
4. Keep future added cases blocked until their context, facts, approval record, exact-value ledger, and unit gates pass.
5. Only then run a full noisy Gold-vs-Pipeline benchmark and report it as mainline evidence.
