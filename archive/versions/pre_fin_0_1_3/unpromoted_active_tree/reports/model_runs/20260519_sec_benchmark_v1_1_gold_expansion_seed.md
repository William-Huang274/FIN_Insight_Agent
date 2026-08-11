# Model Run: 20260519_sec_benchmark_v1_1_gold_expansion_seed

## Summary
- Purpose: 在 reviewed10 baseline 之后，新增一组 v1.1 gold expansion seed cases，用于后续检验 Judgment Plan、table-cell/derived-cell contract、metric-definition caveat 和 pipeline gates 的泛化能力。
- Status: seed-only completed
- Run type: case-spec scaffold + seed evidence build + readiness smoke
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent`

## Code And Command
- Git commit: `820df59`
- Dirty files: 当前工作区已有大量未提交实验产物；本轮新增 v1.1 expansion case spec、seed context/fact candidates、readiness/seed reports 和 worklog。
- Main commands:

```powershell
python scripts\build_sec_gold_context_seed.py `
  --cases-path eval\sec_cases\test_cases_v1_1_gold_expansion.jsonl `
  --report-path reports\quality\sec_benchmark_v1_1_gold_expansion_seed_report.json `
  --evidence-top-k 4 `
  --object-top-k 5

python scripts\validate_sec_benchmark.py `
  --cases-path eval\sec_cases\test_cases_v1_1_gold_expansion.jsonl `
  --output-path reports\quality\sec_benchmark_v1_1_gold_expansion_readiness.json `
  --run-bm25-smoke `
  --bm25-top-k 5
```

## Inputs
- Expansion case spec: `eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl`
- Evidence store: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`
- Object BM25 index: `data/indexes/bm25/sec_tech_10k_objects`
- Evidence BM25 index: `data/indexes/bm25/sec_tech_10k`

## Outputs
- Seed report: `reports/quality/sec_benchmark_v1_1_gold_expansion_seed_report.json`
- Readiness report: `reports/quality/sec_benchmark_v1_1_gold_expansion_readiness.json`
- Seed context candidates:
  - `eval/sec_cases/gold_context/SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001.jsonl`
  - `eval/sec_cases/gold_context/CAPEX_FCF_TABLE_2023_2025_DIAG_001.jsonl`
  - `eval/sec_cases/gold_context/SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001.jsonl`
  - `eval/sec_cases/gold_context/ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001.jsonl`
- Seed fact candidates:
  - `eval/sec_cases/gold_facts/SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001.json`
  - `eval/sec_cases/gold_facts/CAPEX_FCF_TABLE_2023_2025_DIAG_001.json`
  - `eval/sec_cases/gold_facts/SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001.json`
  - `eval/sec_cases/gold_facts/ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001.json`

## Results
- Added 4 L4 expansion cases:
  - `SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001`: NVDA vs AMD durability and risk comparability.
  - `CAPEX_FCF_TABLE_2023_2025_DIAG_001`: OCF, capex/PP&E purchases, and FCF proxy table.
  - `SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001`: Adobe/Snowflake/Palo Alto ARR/RPO/billings/consumption visibility.
  - `ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001`: Alphabet vs Meta ads recovery, AI infrastructure, and operating leverage.
- Seed build: `case_count=4`, `created_count=4`, `context_row_count=526`, `fact_row_count=208`.
- Per-case seed sizes:
  - Semiconductor durability: 83 context rows, 29 fact candidates.
  - Capex/FCF table: 222 context rows, 120 fact candidates.
  - Subscription visibility comparison: 121 context rows, 37 fact candidates.
  - Ads/AI infra growth quality: 100 context rows, 22 fact candidates.
- Readiness + BM25 smoke: `pass_count=4`, `fail_count=0`, `hard_failure_types={}`, `warning_types={}`.

## Experiment Governance
- Hypothesis: reviewed10 baseline needs new gold cases that stress different failure modes before any full noisy benchmark claim.
- Decision target: add expansion case specs without altering frozen `test_cases_v1.jsonl`, generate seed candidates, and confirm source/index readiness with zero hard failures.
- Ceiling / upper bound: This is seed-only. These files cannot enter mainline scored gates until manually reviewed/trimmed and added to an approval file.
- Baselines to beat: reviewed10 covers current v1 cases but does not sufficiently test AMD, derived FCF, ARR/RPO/billings definition discipline, or ads/AI infrastructure growth-quality judgment.
- Split and leakage guard: Uses local SEC filing artifacts and indexes only; no external data, no cloud credentials, and no model inference.
- Decision label: proceed to reviewed gold construction for selected cases.
- Mainline decision: Do not add these cases to reviewed approval until reviewed context/facts and any required new validators pass.

## Caveats And Next Step
- Not run: no true-Qwen synthesis, no reviewed gold gate, no exact ledger rebuild, no post-gates.
- Known risks: seed candidates are intentionally noisy. Capex/FCF needs derived-cell validation; subscription visibility may need NA/metric-definition gate; semiconductor and ads cases may need abstract rubric entries.
- Next decision: review `SEMICONDUCTOR_DURABILITY` and `CAPEX_FCF_TABLE` first, because they separately stress Judgment Plan generalization and table/derived-cell generalization.
