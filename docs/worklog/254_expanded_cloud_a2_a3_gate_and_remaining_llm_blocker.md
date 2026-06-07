# 254 Expanded Cloud A2/A3 Gate And Remaining LLM Blocker

日期：2026-06-07

## 问题

上一轮会话丢失后，需要重新同步本地、云端和工作日志状态，并继续执行 `docs/architecture/expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md` 里的扩容后分层门控。此前本地 full238 A1-A5 已通过，但云端 true expanded gate 卡在 A2/S3，不能继续宣称 expanded full-chain。

## 同步结论

云端工作区：

- Workspace：`/root/autodl-tmp/fin_agent_sp500_stage/workspace`
- Python venv：`/autodl-fs/data/fin_agent_milvus_bge_m3/.venv/bin/python`
- Expanded SEC evidence：`/autodl-fs/data/fin_agent_milvus_bge_m3/data/evidence/tier1_tier2_sec_full_source_mixed_evidence_fy2023_2027_v0_1.jsonl`
- Expanded BM25：`/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1`
- Expanded Object SQLite FTS：`/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/sqlite_fts/tier1_tier2_sec_full_source_mixed_objects_fy2023_2027_v0_1`
- BGE model：`/autodl-fs/data/fin_agent_milvus_bge_m3/models/bge-m3-local`
- Focused A2 ledger：`/autodl-fs/data/fin_agent_milvus_bge_m3/ledger/20260607_tier1_tier2_sec_full_source_focused_a2_ledger_from_object_sqlite_v0_2.duckdb`

云端仍未定位到 verified full combined Tier1+Tier2 exact-value ledger；本轮 focused ledger 只覆盖 A2 四个 gate case 需要的 `AMZN/MSFT/NVDA/AMD/GOOGL`、`2025/2026`、`10-K/10-Q` primary SEC metric/table rows，不能替代完整 combined ledger。

## 修复与执行

1. 修复 SEC form scope 推断：
   - `mcp_tool_registry` / `project_inventory` / BM25 / ObjectBM25 / Object SQLite build / benchmark runner / cloud interactive source resolver 均支持从 legacy evidence/object id 和 `source_type` 推断 `8-K/10-K/10-Q/20-F/40-F/6-K`。
   - 解决 AMZN 2026 8-K 已在 manifest 但被 A2 source resolver 误判缺失的问题。

2. 构建 focused A2 exact-value ledger：
   - 第一次 v0_1 使用 `source_tier` 单列索引扫描，进程超过 12 分钟且 DuckDB 仍只有 12KB，已终止为 partial diagnostic。
   - v0_2 改为按 `ticker/fiscal_year/form/object_type` 分组命中 SQLite 复合索引，并用 `LedgerStoreBulkCsvWriter` CSV copy 写入。
   - v0_2 结果：source records `13584`，ledger facts `11280`，elapsed `4.573s`。
   - MSFT capex probe：`6` rows。

3. 修复 `margin` exact ledger 查询：
   - A2 AMZN case 的 planner 参数是 `metric_families=["margin"]`，但 AMZN primary filing 中没有直接披露为 `gross_margin` 的百分比 ledger row。
   - `src/sec_agent/ledger_store.py` 将 `margin` 扩展为 `gross_margin / operating_margin / operating_income / net_income / revenue / total_revenue`，返回可审计的利润率基础项，不伪造派生 margin 数字。
   - AMZN `margin` probe 变为 `12` rows；A2 AMZN smoke v0_6 通过，runtime ledger rows `111`。

4. 补齐云端 market/industry 产物：
   - 云端原先不存在默认 market/industry evidence 路径，A2 full v0_1 的 market/industry tool 读 0 rows。
   - 从本地上传：
     - `data/processed_private/market/evidence_packs/20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1_3m_market_evidence.jsonl`，`238` rows。
     - `data/processed_private/market/catalog.duckdb`
     - `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales/industry_evidence_rows.jsonl`，`36` rows。
     - `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales/industry_snapshot.duckdb`

5. 修复 stale summary `output_dir`：
   - S2 relationship summary 中的 `output_dir` 是本地 Windows 绝对路径；云端 A2/A3 直接信任该字段会读不到 relationship artifacts。
   - `scripts/eval_multi_agent/eval_multi_agent_evidence_operator_gate.py` 新增 `_summary_artifact_root(...)`：summary `output_dir` 存在才使用，否则回退到 summary JSON 所在目录。
   - `scripts/eval_multi_agent/eval_multi_agent_coverage_reflection_gate.py` 复用同一 helper。

## 云端门控结果

### A2/S3

Accepted diagnostic run：

- Run ID：`20260607_expanded_a2_cloud_sec_expanded_operator_gate_v0_2`
- Output：`eval/sec_cases/outputs/multi_agent_evidence_operator_diagnostic/20260607_expanded_a2_cloud_sec_expanded_operator_gate_v0_2/evidence_operator_diagnostic.json`
- Gate：`pass`
- Case：`4/4`
- Tool calls：`14`
- SEC context rows：`146`
- Runtime ledger rows：`383`
- Market rows：`4`
- Industry rows：`10`
- Relationship lookup / plan rows：deep case `42/42`
- SEC pre-rerank candidates：`550`
- BGE candidates：`433`

Case detail：

- `ma_msft_capex_lookup`：pass，runtime ledger rows `6`。
- `ma_amzn_margin_focused`：pass，context rows `6`，runtime ledger rows `111`。
- `ma_nvda_amd_market_standard`：pass，context rows `20`，runtime ledger rows `126`，market rows `2`。
- `ma_ai_capex_supply_chain_deep`：pass，context rows `120`，runtime ledger rows `140`，market rows `2`，industry rows `10`，relationship rows `42/42`。

### A3/S4

Accepted diagnostic run：

- Run ID：`20260607_expanded_a3_cloud_coverage_reflection_gate_v0_1`
- Output：`eval/sec_cases/outputs/multi_agent_coverage_reflection_diagnostic/20260607_expanded_a3_cloud_coverage_reflection_gate_v0_1/coverage_reflection_diagnostic.json`
- Gate：`pass`
- Case：`4/4`
- second-pass allowed：`1`
- second-pass ran：`1`
- second-pass added rows：`0`
- missing requirement count：`1`

该结果说明 Coverage / Reflection 能正确识别 source-gap boundary 和 no-gain second-pass，不说明缺口被补齐。

## 剩余阻塞

- 云端没有 LLM provider key：`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`DASHSCOPE_API_KEY`、`SILICONFLOW_API_KEY` 均未设置。因此 A4/S5 Specialist 和 A5/S6-S8 Judgment/Memo/Verifier 不能在云端继续主线运行。
- focused A2 ledger 不能替代 full combined Tier1+Tier2 ledger。进入 expanded full-chain 前仍需定位或重建 verified combined ledger。
- 本轮上传的 market/industry 是 full238 旧产物，用于复现 A2 gate 需求；不是 603-company expanded market/industry 主线产物。

## 本地验证

- `python -m py_compile src\sec_agent\ledger_store.py scripts\eval_multi_agent\eval_multi_agent_evidence_operator_gate.py scripts\eval_multi_agent\eval_multi_agent_coverage_reflection_gate.py src\sec_agent\mcp_tool_registry.py src\sec_agent\project_inventory.py src\retrieval\bm25_retriever.py src\retrieval\object_bm25_retriever.py src\indexing\build_object_sqlite_fts_index.py scripts\eval_sec_benchmark\run_sec_benchmark_eval.py scripts\cloud\sec_agent_interactive.py`
- `python -m pytest tests\test_sec_agent_ledger_store.py tests\test_eval_multi_agent_gate_config_roundtrip.py -q` -> `16 passed`
- 早前 targeted regressions：BM25/ObjectBM25 8-K inference、SEC MCP runtime tools、project inventory、8-K benchmark source resolver 均已通过。

## 下一步

- 配置云端 LLM provider key 后，复用 A1/S1、S2、A2 v0_2、A3 v0_1 artifacts 跑 A4/S5 和 A5/S6-S8。
- 定位或重建 full combined Tier1+Tier2 exact-value ledger，并替换 focused A2 ledger rerun A2/A3，确认不是 focused artifact 偶然通过。
- 若要主线化 603-company expanded path，补齐 603-company market/industry merged evidence/catalog，而不是依赖 full238 旧产物。
