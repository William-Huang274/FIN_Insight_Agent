# Handoff - v2 Plus4 AMZN Reviewed-Gold Next

Date: 2026-05-19

## 当前结论

当前 v2 主线已经从 plus3 推进到 plus4 reviewed-gold artifact：

- 新增 case: `AMZN_AWS_NUMERIC_2023_2025_001`
- 新 manifest: `eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl`
- v2 当前规模: 10 total cases, 9 reviewed non-trap cases, 1 trap case
- 本轮只完成 reviewed-gold artifact 和 deterministic gates
- 还没有跑 BGE-M3 pipeline-context trace、Judgment Plan、RTX 5090 Qwen9B 推理或 full post-gates

关键判断：

- plus4 artifact 本身可以进入 case-filtered pipeline smoke。
- 不能把 plus4 当前状态说成模型输出已验证。
- 不能说 full v2 benchmark 或 MVP 已通过。
- BGE-M3 路线必须继续固定为 final context selector；BM25/ObjectBM25 只能是 candidate generator。

## 新窗口优先读这些文件

1. `docs/worklog/99_sec_benchmark_v2_pilot_plus4_amzn_reviewed_gold_audit.md`
2. `reports/model_runs/20260519_sec_benchmark_v2_pilot_plus4_reviewed_gold_gates.md`
3. `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_build_report.json`
4. `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json`
5. `eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl`
6. `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json`
7. `docs/eval/sec_benchmark_v2_next_reviewed_batch_design.md`
8. `docs/worklog/98_sec_benchmark_v2_next_reviewed_batch_design.md`
9. `docs/worklog/97_sec_benchmark_v2_pilot_plus3_snow_bge_m3_qwen9b_5090_audit.md`
10. `reports/model_runs/20260519_sec_benchmark_v2_pilot_plus3_snow_bge_m3_qwen9b_5090.md`

## 最近完成的关键工作

新增脚本：

- `scripts/build_sec_benchmark_v2_pilot_plus4_reviewed_gold.py`

它做了这些事：

- 从 `eval/sec_cases/test_cases_v2_pilot_plus3_seed.jsonl` 生成 plus4 manifest。
- 从 `eval/sec_cases/test_cases_v1.jsonl` 继承 AMZN AWS 原始 case。
- 复用已人工 reviewed 的 AMZN assets：
  - `eval/sec_cases/reviewed_gold_context/AMZN_AWS_NUMERIC_2023_2025_001.jsonl`
  - `eval/sec_cases/reviewed_gold_facts/AMZN_AWS_NUMERIC_2023_2025_001.json`
- 给 AMZN case 补 v2 字段：
  - `case_family=v2_pilot_plus4`
  - `test_objective`
  - `required_caveats`
  - `disallowed_claims`
  - 更严格的 hard gates / hallucination traps / failure types
- 生成：
  - `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json`
  - `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_build_report.json`

## Deterministic Gate 结果

已通过：

- readiness: 10/10 pass
- reviewed-gold mainline gate: 9/9 pass
- trap smoke: 1 trap pass, 9 skipped_not_applicable
- exact-value ledger: 86 rows
- ledger-unit: 86/86 pass

对应路径：

- `reports/quality/sec_benchmark_v2_pilot_plus4_readiness.json`
- `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_gate_mainline.json`
- `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_gate_trap_smoke.json`
- `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json`
- `reports/quality/sec_benchmark_v2_pilot_plus4_ledger_unit_gate.json`

## BGE-M3 路线约束

不要回到 BM25-only。

plus4 build report 已写入：

- `final_context_selector=BAAI/bge-reranker-v2-m3`
- `bm25_role=candidate_generator_only`
- `bm25_only_allowed=false`

后续 pipeline-context 应沿用 plus3 的形态：

- BM25/ObjectBM25 生成候选
- BGE-M3 reranker 做最终 context selection
- Judgment Plan 基于 BGE trace + exact-value ledger 生成
- Qwen9B resident vLLM 在 RTX 5090 32GB 上跑 synthesis
- post-gates 必须包含 caveat/claim、v2 semantic、answer-vs-plan、metric-source grounding、ledger-unit 等 gate

## 关键命令记录

本轮已执行并通过的本地命令：

```bash
python scripts/build_sec_benchmark_v2_pilot_plus4_reviewed_gold.py

python scripts/validate_sec_benchmark.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --output-path reports/quality/sec_benchmark_v2_pilot_plus4_readiness.json

python scripts/validate_sec_gold_gate.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --gold-facts-dir eval/sec_cases/reviewed_gold_facts \
  --manual-review-path reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json \
  --gate mainline_scored \
  --case-id META_REALITY_LABS_2024_001 \
  --case-id PANW_RPO_BILLINGS_NUMERIC_2023_2025_001 \
  --case-id GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001 \
  --case-id AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001 \
  --case-id AMD_SEGMENT_MIX_2023_2025_001 \
  --case-id ADBE_DIGITAL_MEDIA_ARR_REVENUE_GROWTH_2023_2025_001 \
  --case-id GOOGL_META_ADS_AI_INFRA_LOCAL_SUPPORT_2023_2025_001 \
  --case-id SNOW_NRR_RPO_GROWTH_2023_2025_001 \
  --case-id AMZN_AWS_NUMERIC_2023_2025_001 \
  --output-path reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_gate_mainline.json

python scripts/validate_sec_gold_gate.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --gold-facts-dir eval/sec_cases/reviewed_gold_facts \
  --manual-review-path reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json \
  --gate trap_smoke \
  --output-path reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_gate_trap_smoke.json

python scripts/build_sec_benchmark_exact_value_ledger.py \
  --reviewed-facts-dir eval/sec_cases/reviewed_gold_facts \
  --approval-path reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json \
  --output-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json

python scripts/validate_sec_benchmark_ledger_units.py \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json \
  --output-path reports/quality/sec_benchmark_v2_pilot_plus4_ledger_unit_gate.json
```

## 新窗口推荐下一步

有两个合理分支。

### 分支 A: 先跑 plus4 pipeline

目的：验证 AMZN AWS case 加入后，当前 BGE-M3 + Judgment Plan + Qwen9B 链路是否仍然过 full post-gates。

建议先沿用 plus3 的参数，只替换 plus4 路径和 run id：

- cases: `eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl`
- ledger: `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json`
- trace run id 建议:
  `run_20260519_v2_pilot_plus4_pipeline_context_bge_m3_top160_object8_local`
- Qwen run id 建议:
  `run_20260519_v2_pilot_plus4_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`
- post-gate output dir 建议:
  `reports/quality/local_v2_pilot_plus4_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates`

注意：

- 云端 RTX 5090 32GB 可用，但不要把 SSH 密码写进任何文档。
- 远端路径沿用此前约定：
  `/root/autodl-tmp/FIN_Insight_Agent`
- 硬件 profile 沿用：
  `rtx5090_32gb`
- 保留 4090 配置，不要删除或覆盖。

### 分支 B: 继续扩第二个 case

目的：先把下一批 reviewed cases 做厚一点，再统一跑 pipeline。

推荐下一个 case：

- `AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001`

构建原则：

- 不直接 promote broad `CLOUD_PROFITABILITY_2023_2025_DIAG_001`。
- 从 broad cloud profitability reviewed facts/context 中只切 AMZN/GOOGL 子集。
- 明确比较边界：AWS vs Google Cloud 的 segment revenue 和 operating income。
- 不加入 Microsoft，因为 Microsoft Cloud 是 broad proxy，跟 AWS/Google Cloud segment operating income 不可直接同口径比较。
- 新 case 必须加 v2 caveat/claim 字段，然后重跑 readiness、gold、ledger、unit gates。

## 当前风险和注意事项

- 当前工作区是 dirty 的，很多文件是历史 untracked artifact。不要做 destructive git 操作。
- `docs/worklog/10_engineering_phase1_foundation.md` 显示为 modified，但本轮没有处理它；不要回滚。
- 本轮新增的 plus4 只是 artifact/gate 层，不包含模型输出质量结论。
- AMZN 的重点风险是模型把 YoY percentage 当成 dollar revenue，或把 AWS operating income 当成 margin。
- plus4 manifest 已用 `disallowed_claims` 和 `required_caveats` 显式暴露这些风险，后续 Qwen 输出必须被 caveat/claim gate 和 semantic gate 检查。
- 如果跑 plus4 pipeline 后出现失败，应先看是否是 retrieval trace 中 AMZN AWS source evidence / metric IDs 缺失，再看 synthesis，而不是直接调 prompt。

## 交接状态

建议新窗口从分支 A 开始：先跑 plus4 pipeline-context true-Qwen，确认单 case 增量没有破坏全链路。若 plus4 post-gates 过，再继续构建 AMZN/GOOGL cloud profitability case。

本交接未包含任何密码、token 或临时凭证。
