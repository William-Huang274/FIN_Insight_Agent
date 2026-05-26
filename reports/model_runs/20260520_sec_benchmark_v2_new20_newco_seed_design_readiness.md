# Model Run: 20260520_sec_benchmark_v2_new20_newco_seed_design_readiness

## Summary

- Purpose: Design new-company SEC benchmark cases for the expanded 20-company universe and verify source/index readiness before reviewed-gold promotion or Qwen inference.
- Status: completed
- Run type: deterministic case-design build + retrieval readiness smoke
- Timestamp: 2026-05-20 Asia/Shanghai
- Environment: local Windows repo for manifest generation; cloud RTX 5090 machine for 20-company readiness/BM25 smoke.

## Code And Command

- Entry points:
  - `scripts/build_sec_benchmark_v2_new20_newco_seed.py`
  - `scripts/validate_sec_benchmark.py`
- Local command:

```powershell
python scripts/build_sec_benchmark_v2_new20_newco_seed.py
python -m py_compile scripts/validate_sec_benchmark.py scripts/build_sec_benchmark_v2_new20_newco_seed.py
```

- Cloud readiness command:

```bash
/root/miniconda3/bin/python scripts/validate_sec_benchmark.py \
  --cases-path eval/sec_cases/test_cases_v2_new20_newco_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --output-path reports/quality/sec_benchmark_v2_new20_newco_seed_readiness_bm25_smoke.json \
  --run-bm25-smoke \
  --bm25-top-k 5
```

- Config: `configs/sec_tech_universe.yaml`
- Seeds: deterministic script, no random seed.

## Inputs

- Data profile: cloud 20-company SEC 10-K corpus, fiscal 2023-2025.
- Source/index artifacts:
  - `data/processed_private/manifests/sec_tech_10k_manifest.jsonl`
  - `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`
  - `data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl`
  - `data/indexes/bm25/sec_tech_10k`
  - `data/indexes/bm25/sec_tech_10k_objects`
- Candidate boundary:新增 10 家公司 `AVGO/CSCO/INTC/QCOM/TXN/AMAT/MU/INTU/ADP/CRWD`.
- Label protocol: seed design only; reviewed context/facts not generated in this run.

## Outputs

- Case manifest:
  `eval/sec_cases/test_cases_v2_new20_newco_seed.jsonl`
- Design report:
  `reports/quality/sec_benchmark_v2_new20_newco_seed_design_report.json`
- Readiness/BM25 smoke report:
  `reports/quality/sec_benchmark_v2_new20_newco_seed_readiness_bm25_smoke.json`
- Worklog:
  `docs/worklog/115_sec_benchmark_v2_new20_newco_case_design.md`

## Results

- New cases: 10
- Company coverage: 10/10新增公司
- Readiness pass_count: 10/10
- Readiness fail_count: 0
- Hard failures: none
- Warnings: `gold_context_missing=10`, expected because all cases intentionally remain `seed_needs_review`.
- No Qwen inference, BGE-M3 trace, Judgment Plan, exact-value ledger, or post-gates were run.

## Experiment Governance

- Hypothesis: new-company benchmark cases must be designed and source-ready before Qwen outputs can support 20-company generalization claims.
- Decision target: 10/10 new-company cases pass source/index readiness and BM25/ObjectBM25 smoke with no hard failures.
- Ceiling: seed-only. This run cannot support reviewed-gold or model-quality claims.
- Baselines to beat: existing 10-company full40 reviewed diagnostic route and 20-company source/index build.
- Leakage guard: case definitions are fixed before reviewed fact/context generation and before any Qwen output on these cases.
- Stop conditions: stop before Qwen quality inference if any source/index readiness hard failure appears.
- Efficiency gate: deterministic generation plus BM25/ObjectBM25 smoke only; no GPU inference.
- Decision label: `proceed_to_newco_seed_readiness_only`.
- Mainline decision: proceed to reviewed context/facts build; blocked from scored benchmark claims.

## Runtime Efficiency

- Wall time: local generation and compile under 1 second; cloud readiness/BM25 smoke about 12 seconds.
- GPU utilization: none.
- Throughput: 10 case readiness checks over 30 required filings.
- Bottleneck diagnosis: no bottleneck at seed/readiness scale.
- Serving latency implication: none; this was not a serving or model inference run.

## Caveats And Next Step

- Not run: reviewed context/facts generation, exact-value ledger, ledger-unit gate, BGE-M3 trace, Judgment Plan, Qwen9B or 27B inference.
- Known risks: some case metrics need manual fact selection because structured objects can contain multiple table variants or disclosure-scope rows.
- Next decision: build reviewed context/facts for these 10 cases from cloud structured objects, then run gold/ledger gates before any quality benchmark.
