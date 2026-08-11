# 246 - Tier1/Tier2 市场行业数据接入与扩容后 Agent 架构计划

日期：2026-06-06

## 本轮目标

在云端 Milvus full evidence build 继续运行时，不等待空转，先把 Tier1+Tier2 `603` 家公司的市场/行业数据接入到可用 staging artifact，并规划扩容后多智能体链路如何消费新数据、Milvus typed semantic recall、关系图谱和更大的上下文。

## 市场数据结果

新增脚本：

- `scripts/data_expansion/build_market_industry_expansion_manifests.py`

新增 manifest：

- `data/manifests/tier1_tier2_market_universe_v0_1.csv`
- `data/manifests/tier1_tier2_market_yahoo_tickers_v0_1.yaml`
- `data/manifests/tier1_tier2_industry_source_family_map_v0_1.jsonl`
- `data/manifests/tier1_tier2_market_industry_manifest_summary_v0_1.json`

真实运行：

- Yahoo 1Y daily bars：`603` 个目标 ticker + `SPY/QQQ`，全部成功。
- normalized market snapshots：`603` rows。
- daily bars：`151320` rows。
- market analytics：`603` rows。
- market evidence pack：`603` rows。
- catalog DuckDB：已生成。
- validation：pass，`can_enter_market_snapshot_chain=true`。

注意事项：

- 大多数 ticker 最新交易日为 `2026-06-05`；`CTRA` provider latest date 为 `2026-05-07`，需在 market evidence 里保留 stale caveat。
- FMP key-metrics 小样本能补美国 ticker 的 `market_cap / enterprise_value / ev_sales_ttm / ev_ebitda_ttm`。
- FMP 全量并发触发 `429 Too Many Requests`，产物字段覆盖为 0，不能作为估值快照使用。
- 非美本地交易所代码在 FMP free endpoint 下返回 402 或不可用，后续要用当地交易所、公司披露或合规 provider 补估值。

脚本修复：

- `scripts/market/07_enrich_market_snapshot_valuation_fmp.py` 增加 `--workers` 和 `--skip-ticker-regex`，并修复“空 valuation dict 被误计为 enriched ticker”的口径 bug。

## 行业数据结果

脚本修复：

- `scripts/industry/10_download_industry_source_snapshot.py`
  - 增加请求重试参数。
  - 增加 `--allow-source-failures`，把慢源或不可用源写入 metadata，而不是让整批不可用。
  - 增加 `--provider-filter`、`--source-family-filter`、`--series-id-filter`，支持分源运行。
- `scripts/industry/20_merge_industry_source_snapshots.py`
  - 新增 provider-specific industry snapshot 合并脚本。
- Workbench source 合同扩展：
  - `SourceArtifactsProfile` 增加 `industry_evidence_path`、`industry_snapshot_db_path`、`industry_snapshot_id`、`industry_as_of_date`。
  - Source bundle 增加行业 evidence / DuckDB artifact 字段。
  - Source readiness 增加行业 evidence 摘要，统计 source family、provider 和 as-of date。
  - Data build step 支持 provider/source-family/series 过滤、source failure 记录，并能把行业 snapshot artifact 写回 source bundle。

真实运行：

- EIA-only snapshot：`10315` observations、`2` evidence rows、`0` failures。
- FRED-only snapshot：`17435` observations、`21` evidence rows、`11` failures。
- FRED+EIA merged snapshot：`27750` observations、`23` evidence rows、`11` failures。

FRED 缺口：

- 利率/信用：`DGS10`、`DGS2`、`BAA10Y`。
- 消费：`PCE`、`UMCSENT`。
- 能源：`DCOILWTICO`、`DCOILBRENTEU`、`DHHNGSP`。
- 材料/住房：`WPU10`、`WPU101`、`MORTGAGE30US`。

结论：

- 行业 snapshot 已足够作为 context-only source 接入 agent。
- 缺失 FRED series 只能作为 source gap，不允许 Specialist 或 Memo Writer 用模型常识补。
- 后续要把 FRED 改为分 series 缓存/异步补齐，避免慢源拖住整批。

## 云端 Milvus 和 retrieval-only A/B 状态

云端 full evidence build 已完成：

- run id：`20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2`
- evidence rows：`231842`
- collection rows：`662908`
- embedding device：`cuda`
- vector kind：`narrative_chunk=231842`、`paraphrase_context=217709`、`table_chunk=107007`、`relationship_context=106350`
- build summary：`/autodl-fs/data/fin_agent_milvus_bge_m3/outputs/milvus_retrieval_ab/20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2/milvus_retrieval_ab_summary.json`

同时在云端为同一份 expanded evidence 重建 BM25 baseline：

- path：`/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1`
- records：`231842`

retrieval-only A/B：

- run id：`20260606_tier1_tier2_sec_full_source_milvus_bge_m3_retrieval_ab_bm25_hybrid_v0_1`
- gate：pass
- cases：`12/12`
- exact lookup：`2/2`
- sector-depth：`6/6`
- relationship：`2/2`
- paraphrase：`2/2`
- mean BM25 usable evidence rows：`19.5`
- mean Milvus usable evidence rows：`14.5833`
- mean Hybrid usable evidence rows：`19.1667`
- summary：`/autodl-fs/data/fin_agent_milvus_bge_m3/outputs/milvus_retrieval_ab/20260606_tier1_tier2_sec_full_source_milvus_bge_m3_retrieval_ab_bm25_hybrid_v0_1/milvus_retrieval_ab_summary.json`

边界：

- 本轮 A/B 禁用 ObjectBM25 baseline，因为 expanded 结构化对象 SQLite/FTS baseline 尚未在云端重建。
- 不能拿旧 full238 ObjectBM25 与 603 家 Milvus 对比。
- Milvus 通过 retrieval-only gate 不等于可以直接进入 full-chain；仍需 A1-A5 分层 agent gate。

## 新增架构文档

新增：

- `docs/architecture/expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md`

核心内容：

- 明确 SEC、exact-value ledger、市场快照、行业快照、关系图谱和 Milvus 的 source boundary。
- 规划 `resolve_universe_scope`、`build_retrieval_intent_plan`、`relationship_graph_expand`、`execute_evidence_operators`、`evidence_fusion_selector`、`specialist_dispatch`、`judgment_aggregator`、`memo_writer`、`verifier_quality_gate` 的节点调整。
- 规划 Research Lead、Universe/Relationship、Fundamental、Market、Industry/Supply-chain、Risk、Memo Writer 的 role-specific skill vNext。
- 规定 A0-A6 分层门控，要求先分层 gate，再 full-chain / multi-turn。

## 验证

已通过：

- `python -m pytest tests\test_market_industry_expansion_manifests.py -q`
- `python -m pytest tests\test_industry_source_snapshot.py -q`
- `python -m pytest tests\test_market_snapshot_fixture.py -q`
- `python -m pytest tests\test_workbench_profiles.py tests\test_industry_source_snapshot.py tests\test_market_snapshot_fixture.py tests\test_market_industry_expansion_manifests.py -q`
- `python -m compileall scripts\market\07_enrich_market_snapshot_valuation_fmp.py scripts\industry\10_download_industry_source_snapshot.py scripts\industry\20_merge_industry_source_snapshots.py`

## 下一步

1. 重建 expanded ObjectBM25 / SQLite FTS baseline，补 exact/metric retrieval 对照。
2. 把 market/industry merged artifacts 写入 source inventory。
3. 更新 Evidence Operator 和 Evidence Fusion Selector，让 market/industry/Milvus 进入分层 agent gate。
4. 更新 Research Lead 与 Specialist skill vNext。
5. 只跑分层 A1-A5 gate；通过后再跑 full-chain。

敏感信息检查：

- API key 只用于进程环境变量，没有写入脚本、文档或 artifact metadata。
- artifact metadata 中的 EIA URL 已按脚本规则 redacted。
