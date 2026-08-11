# 247 Expanded Object SQLite FTS And Object-Hybrid Retrieval A/B

日期：2026-06-07

## Prompt

用户要求根据最新 architecture 文档、工作日志、本地和云端已完成事项先同步工作进度，避免和上一会话交接断裂，然后按文档步骤继续未完成事项。

## Progress Sync

- 当前分支仍是 `codex/layered-data-source-expansion`，HEAD 为 `abf26ae Harden workbench runtime edges`；本轮分层数据源扩容工作仍主要在未提交工作区和云端 staging 产物中。
- 本地最新 durable worklog 到 `246_tier1_tier2_market_industry_and_agent_framework_plan.md`，architecture 文档包括：
  - `docs/architecture/layered_data_source_expansion_plan.zh-CN.md`
  - `docs/architecture/layered_data_source_expansion_execution_plan.zh-CN.md`
  - `docs/architecture/expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md`
- 已确认云端 staging 资产：
  - expanded evidence：`231842` rows。
  - expanded BM25：`/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1`，约 `1.9G`。
  - expanded Object SQLite FTS：`/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/sqlite_fts/tier1_tier2_sec_full_source_mixed_objects_fy2023_2027_v0_1`，metadata 记录 `7493637` records，约 `14G`。
  - expanded Milvus typed semantic DB：`/autodl-fs/data/fin_agent_milvus_bge_m3/milvus/20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2`，`662908` vectors，约 `5.2G`。
  - Tier1 cloud full ledger：`/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/indexes/staging/ledger/tier1_sp500_us_annual_10k_fy2023_2025_v0_1_full_ledger.duckdb`，`4810839` facts，约 `990.76MB`。
- 需要避免误交接的边界：
  - `expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md` 曾记录 combined exact-value ledger `6789032` facts，但本轮云端只找到 Tier1 full ledger 和本地记录的 Tier2 SEC ledger；未找到可验证的 combined ledger DuckDB。后续在使用 `6789032` 口径前必须先定位或重建 combined ledger。
  - 2026-06-07 早些时候云端留下的 `object_hybrid_v0_1/v0_2` 和 `ai_sector_smoke` 目录为空或没有 summary，不能算通过；对应日志尾部有 Milvus gRPC `too_many_pings`，本轮不把这些 run 当成证据。

## Work Completed

- 更新 retrieval-only A/B 脚本报告合同：
  - `scripts/eval_retrieval/eval_milvus_retrieval_ab.py`
  - summary 现在显式输出：
    - `mean_object_bm25_usable_evidence_rows`
    - `mean_object_bm25_metric_evidence_rows`
    - `object_bm25_enabled_case_count`
    - `exact_object_metric_hit_pass_count`
  - markdown case table 增加 Object usable 和 Object metric 列。
- 新增目标测试：
  - `tests/test_milvus_retrieval_ab_design.py`
  - `test_summary_exposes_object_bm25_baseline_metrics`
- 云端同步脚本到：
  - `/autodl-fs/data/fin_agent_milvus_bge_m3/scripts/eval_retrieval/eval_milvus_retrieval_ab.py`
- 先跑 JPM 1-case object baseline smoke：
  - run id：`20260607_tier1_tier2_object_ab_jpm_smoke_v0_2_summary_metrics`
  - gate：pass
  - case：`1/1`
  - Object usable：`20`
  - Object metric：`20`
  - exact object metric hit：`1/1`
- 再跑 12-case expanded object-hybrid retrieval-only A/B：
  - run id：`20260607_tier1_tier2_sec_full_source_object_hybrid_ab_v0_3`
  - gate：pass
  - cases：`12/12`
  - exact lookup：`2/2`
  - sector-depth：`6/6`
  - relationship：`2/2`
  - paraphrase：`2/2`
  - mean BM25 usable evidence rows：`19.5`
  - mean ObjectBM25 usable evidence rows：`15.25`
  - mean ObjectBM25 metric evidence rows：`9.8333`
  - mean Milvus usable evidence rows：`18.6667`
  - mean Hybrid usable evidence rows：`19.4167`
  - ObjectBM25 enabled case count：`12`
  - exact object metric hit pass count：`2`

## Result And Evidence

- 本地测试：
  - `python -m pytest tests\test_milvus_retrieval_ab_design.py -q`
  - 结果：`9 passed`
- 云端 summary：
  - `/autodl-fs/data/fin_agent_milvus_bge_m3/outputs/milvus_retrieval_ab/20260607_tier1_tier2_sec_full_source_object_hybrid_ab_v0_3/milvus_retrieval_ab_summary.json`
  - `/autodl-fs/data/fin_agent_milvus_bge_m3/outputs/milvus_retrieval_ab/20260607_tier1_tier2_sec_full_source_object_hybrid_ab_v0_3/milvus_retrieval_ab_summary.md`
- Model run ledger：
  - `reports/model_runs/20260607_tier1_tier2_sec_full_source_object_hybrid_retrieval_ab_v0_3.md`

## Decision

- Architecture 文档的下一步第 1 项“重建 expanded ObjectBM25 / SQLite FTS baseline，补 exact/metric retrieval 对照”现在可以标为完成到 retrieval-only diagnostic gate。
- 该结果仍是 retrieval-only / staging diagnostic，不代表 Milvus/ObjectBM25 已进入 full-chain agent 默认路径。
- 下一步按 `expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md` 顺序推进：
  1. 把 market/industry merged artifacts 写入 source inventory，保持 context-only source boundary。
  2. 更新 `execute_evidence_operators`，加入 Milvus typed semantic route 和 expanded market/industry catalog path。
  3. 更新 Evidence Fusion Selector，让不同 Specialist 看到不同 source-family bundle。
  4. 先跑 A1-A5 分层 gate，不直接跑 full-chain。

## Safety Notes

- 没有把 SSH 密码、API key 或私有 token 写入文件。
- 云端只同步了 retrieval A/B 脚本；没有删除、覆盖 raw data、ledger、Milvus DB 或其他 private artifacts。
- 本轮没有运行 LLM full-chain，也没有修改 mainline index 默认路径。
