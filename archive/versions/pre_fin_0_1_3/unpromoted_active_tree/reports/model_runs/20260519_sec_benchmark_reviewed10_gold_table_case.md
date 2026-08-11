# Model Run: 20260519_sec_benchmark_reviewed10_gold_table_case

## Summary
- Purpose: 将 SEC benchmark v1 最后一条未审核的非 trap 表格 case 收成 reviewed10，并确认 gold context / gold facts / exact-value ledger 可进入 case-filtered mainline scored smoke。
- Status: completed
- Run type: artifact build + deterministic validation + context-only smoke
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent`

## Code And Command
- Git commit: `820df59`
- Dirty files: 当前工作区已有较多未提交实验产物；本轮只新增/修改 reviewed10 gold artifacts、case spec、ledger/unit gate validator 与相关 worklog。
- Main commands:

```powershell
python scripts\validate_sec_gold_gate.py --cases-path eval\sec_cases\test_cases_v1.jsonl --gold-context-dir eval\sec_cases\reviewed_gold_context --gold-facts-dir eval\sec_cases\reviewed_gold_facts --manual-review-path reports\quality\sec_benchmark_v1_reviewed_gold_partial_approval.json --gate mainline_scored --case-id AMZN_AWS_NUMERIC_2023_2025_001 --case-id GOOGL_CLOUD_CONTEXT_ROLE_2025_001 --case-id AAPL_SERVICES_MARGIN_2023_2025_001 --case-id PANW_SUBSCRIPTION_VISIBILITY_2023_2025_001 --case-id SNOW_RISK_2023_2025_001 --case-id NVDA_DATACENTER_2023_2025_001 --case-id MSFT_AI_CLOUD_2023_2025_001 --case-id CLOUD_PROFITABILITY_2023_2025_DIAG_001 --case-id PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001 --case-id REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001 --output-path reports\quality\sec_benchmark_v1_gold_gate_reviewed10_text_numeric_cloud_platform_table.json
python scripts\build_sec_benchmark_exact_value_ledger.py --reviewed-facts-dir eval\sec_cases\reviewed_gold_facts --approval-path reports\quality\sec_benchmark_v1_reviewed_gold_partial_approval.json --output-path reports\exact_value_ledgers\sec_benchmark_v1_reviewed_exact_value_ledger.json
python scripts\validate_sec_benchmark_ledger_units.py --ledger-path reports\exact_value_ledgers\sec_benchmark_v1_reviewed_exact_value_ledger.json --output-path reports\quality\sec_benchmark_v1_reviewed10_ledger_unit_gate.json
python scripts\run_sec_benchmark_eval.py --mode gold_context --gold-context-dir eval\sec_cases\reviewed_gold_context --output-dir eval\sec_cases\outputs\run_20260519_reviewed10_gold_context_table_case --case-id REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001 --max-context-rows 80
```

## Inputs
- Case spec: `eval/sec_cases/test_cases_v1.jsonl`
- New reviewed case: `REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001`
- Source structured objects: `data/processed_private/structured_objects/sec_tech_10k_tables.jsonl`
- Reviewed approval: `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`

## Outputs
- Reviewed context: `eval/sec_cases/reviewed_gold_context/REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001.jsonl`
- Reviewed facts: `eval/sec_cases/reviewed_gold_facts/REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001.json`
- Gold gate report: `reports/quality/sec_benchmark_v1_gold_gate_reviewed10_text_numeric_cloud_platform_table.json`
- Exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`
- Ledger unit gate: `reports/quality/sec_benchmark_v1_reviewed10_ledger_unit_gate.json`
- Context-only trace: `eval/sec_cases/outputs/run_20260519_reviewed10_gold_context_table_case`

## Results
- Reviewed case count: 10 non-trap cases approved for case-filtered gold-context scored smoke.
- New case facts: 48 table-derived target cells = 4 companies x 3 fiscal years x 4 consolidated metrics.
- New case context: 56 reviewed rows = 48 reviewed table cells + 8 compact table source rows.
- Gold gate: `can_enter_gate=true`, `case_count=10`, `status_counts={"pass":10}`.
- Exact-value ledger: `approved_case_count=10`, `row_count=98`.
- Ledger unit gate: `can_enter_gate=true`, `pass_count=98`, `fail_count=0`, no warnings.
- Context runner smoke: `trace_count=1`, `agent_output_count=1`, `status_counts={"context_prepared":1}`.

## Experiment Governance
- Hypothesis: v1 最后一条表格 case 可以通过 cell-level reviewed facts 进入 reviewed gold，而不是继续依赖原始 seed 的 224 行上下文和 108 个噪声 fact candidates。
- Decision target: reviewed10 gold gate pass、exact-value ledger pass、unit gate pass、context runner 能消费新 gold context。
- Ceiling / upper bound: 本轮只验证 gold artifact 和 deterministic gates，不声称 pipeline retrieval 或 true-Qwen synthesis 泛化。
- Baselines to beat: 原 seed gold 被拒绝，因为表格上下文和 fact candidates 噪声过高。
- Split and leakage guard: 只使用 repo 内 SEC structured table objects 与 reviewed gold approval；不写入外部凭据，不引入网络数据。
- Decision label: completed for reviewed10 artifact gate; downstream pipeline remains diagnostic-only until reviewed10 pipeline/Judgment Plan run is executed.

## Safety Notes
- 本轮没有跑 true-Qwen synthesis，也没有更新 cloud credential 到任何文件。
- Full noisy benchmark 仍不能直接作为 mainline 结论；下一步应先在 reviewed10 上跑 pipeline-context / Judgment Plan 适配，再扩新 gold cases 做泛化。
