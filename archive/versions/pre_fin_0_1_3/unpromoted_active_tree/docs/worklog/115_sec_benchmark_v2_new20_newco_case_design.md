# SEC Benchmark v2 New20 New-Company Case Design

## Prompt

用户要求先设计新增公司的 reviewed-gold cases，等 Qwen3.6-27B-FP8 下载完成后再做 27B smoke。

## Governance Gate

- Hypothesis: 新增 10 家公司需要先有可审计的 benchmark case 设计，才能把 20 公司语料上的 Qwen 输出解释为新公司泛化证据。
- Decision target: 形成覆盖新增 10 家公司的 case manifest；每个 case 必须能在云端 20 公司 SEC 语料上通过 source/index readiness 和 BM25/ObjectBM25 smoke，且在 reviewed context/facts 尚未生成前保持 `seed_needs_review`。
- Ceiling: 本步骤只允许进入 seed/readiness；不能宣称 new-company reviewed-gold 或 scored Qwen benchmark 质量。
- Baselines: 10 公司 full40 reviewed diagnostic route 已通过；20 公司 SEC source/index build 已完成。
- Split and leakage guard: case prompt、numeric checks、required caveats 和 disallowed claims 先固定；后续 reviewed facts/context 只用于填充证据，不用 Qwen 输出反向改 case 定义。
- Stop conditions: 任一新增公司缺 filing、section、structured metric 或 BM25/ObjectBM25 smoke 失败时，不进入 27B benchmark 质量判断。
- Efficiency gate: readiness smoke 在云端 20 公司 BM25/ObjectBM25 索引上完成，不触发 Qwen inference。
- Decision label: `proceed_to_newco_seed_readiness_only`.

## Work Completed

- 新增 seed builder:
  `scripts/build_sec_benchmark_v2_new20_newco_seed.py`
- 生成 10 个新增公司 case:
  `eval/sec_cases/test_cases_v2_new20_newco_seed.jsonl`
- 生成设计报告:
  `reports/quality/sec_benchmark_v2_new20_newco_seed_design_report.json`
- 修改 readiness validator，使 canonical company set 从
  `configs/sec_tech_universe.yaml` 读取，而不是硬编码旧 10 家:
  `scripts/validate_sec_benchmark.py`
- 在云端 20 公司语料和索引上运行 readiness/BM25 smoke:
  `reports/quality/sec_benchmark_v2_new20_newco_seed_readiness_bm25_smoke.json`

## Case Coverage

新增 10 个 case 覆盖全部 plus10 公司：

- `AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001`
- `CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001`
- `INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001`
- `QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001`
- `TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001`
- `AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001`
- `MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001`
- `INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001`
- `ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001`
- `CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001`

All 10 currently have:

- `reviewed_asset_status=seed_needs_review`
- `gold_context_status=needs_annotation`
- `evaluation_modes=["gold_context","pipeline_context"]`

## Readiness Result

Cloud readiness/BM25 smoke result:

- case_count: 10
- pass_count: 10
- fail_count: 0
- hard_failure_types: `{}`
- warning_types: `{"gold_context_missing": 10}`

The warnings are expected and intentional. They confirm no reviewed context files
exist yet; this prevents accidental promotion to reviewed-gold quality claims.

## 27B Download Status

Qwen3.6-27B-FP8 download completed on cloud before the 27B smoke step:

- Model path:
  `/root/autodl-tmp/FIN_Insight_Agent/data/models_private/modelscope/Qwen/Qwen3___6-27B-FP8`
- Approximate size: 29G
- `/root/autodl-tmp` free space after download: about 49G

No 27B inference was run as part of this case-design gate. The follow-up 27B
deployability smoke is recorded separately in
`docs/worklog/116_qwen36_27b_fp8_5090_smoke.md` and remains diagnostic-only.

## Next Step

1. Build reviewed context/facts for the 10 new-company cases from the cloud 20
   company structured objects.
2. Build a new exact-value ledger and run gold gate plus ledger-unit gate.
3. Only after the reviewed-gold artifacts pass, run BGE-M3 + Judgment Plan +
   Qwen pipeline quality inference on the new-company pack.
4. Qwen3.6-27B-FP8 deployability smoke has been completed separately; keep it
   as runtime feasibility, not benchmark quality.
