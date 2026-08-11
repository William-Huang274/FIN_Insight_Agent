# 408 R42 RD1 Raw Source Provenance Store

日期：2026-06-27

## 问题

RD0 只能说明 raw / processed / index / DB / manifest 资产在哪里、规模多大；用户要求继续按 24 文档推进，因此下一步必须把 runtime-ready rows 追溯到 raw file / URL snapshot / API response / fetch attempt。否则后续 RD2 parser ledger、RD3 fact mart、RD5 retrieval parity 和 RD7 eval gate 都会继续靠散装字段和聊天记忆判断来源。

## 决策

本轮做 RD1 Bronze provenance，不扩大爬虫、不跑 full-chain、不把任何 source 提权。RD1 的职责是建立四类账本：

- `raw_source_document`
- `raw_fetch_attempt`
- `source_snapshot`
- `runtime_row_source_lineage`

同时严格区分：

- `local_raw_snapshot_available` / `api_response_cached`：可回放。
- `runtime_declared_source_document` / `url_only_no_local_snapshot`：能追到 URL，但还没有本地可回放快照。
- `matched_derived_structured_source_document`：派生结构化行回连到本地结构化 raw source。
- unresolved：不能进入后续 exact-authority 主事实层。

## 完成工作

- 新增 `src/sec_agent/raw_source_provenance_store.py`。
  - 扫描 SEC、SEC 8-K、tier1/tier2 annual、SEC structured facts、global public disclosures、company IR 等 raw roots。
  - 解析 `*.metadata.json` / `locator_metadata.json`，生成 source document / snapshot / fetch attempt rows。
  - 为没有 metadata 的 raw files 生成 `raw_file_without_metadata` provenance rows。
  - 自动发现 `data/manifests/*_runtime_rows_v0_1.jsonl`、`*_context_rows_v0_1.jsonl`、`*_metric_slot_rows_v0_1.jsonl`、`*_data_mart_rows_v0_1.jsonl` 作为 runtime rowsets，排除 attempts / rejections / closeout / queue / tmp。
  - 将 runtime rows 反向匹配到 raw path、source URL、external document key 或 SEC CompanyFacts 派生结构化 source。
  - 对 URL query 中的 `crtfc_key`、token、api key 等敏感字段做 redaction，避免把密钥写入 manifest。
- 新增 `scripts/data_expansion/build_raw_source_provenance_store.py`。
- 新增 `tests/test_raw_source_provenance_store.py`。
- 物化 RD1 产物：
  - `data/manifests/raw_source_documents_v0_1.jsonl`
  - `data/manifests/raw_fetch_attempts_v0_1.jsonl`
  - `data/manifests/source_snapshots_v0_1.jsonl`
  - `data/manifests/runtime_row_source_lineage_v0_1.jsonl`
  - `data/manifests/raw_source_provenance_summary_v0_1.json`
  - `docs/internal/vnext_20260610/rd1_raw_source_provenance_store.zh-CN.md`
- 更新 `docs/architecture/agent_graph_vnext/24_raw_disclosure_rag_database_recap_and_data_base_plan.zh-CN.md`，记录 RD1 落地状态。
- 更新 `docs/worklog/00_internal_master_checklist.md`，把 RD1 标为完成并保留 URL-only snapshot debt。

## Root-Cause Fix

第一次真实构建 5 分钟超时。根因不是网络，而是每新增一个 runtime-declared source 都重建一次全量 source map，导致 runtime lineage 循环复杂度过高。本轮改成增量更新 source map 后，真实构建在约 159 秒内完成。

真实构建还暴露 `capital_funding_ownership_context_rows_v0_1` 中 `386` 条 `sec_financial_statement_data_sets` 派生 CapitalStructure rows 丢失 `source_url/raw_path`。本轮没有跳过或降级，而是新增 deterministic resolver：按 `source_id + ticker` 回连本地 SEC CompanyFacts raw API response，并把这类 lineage 标为 `matched_derived_structured_source_document`。最终 exact-authority unresolved 归零。

## 结果

最新 RD1 summary：

- status: `pass`
- raw source documents: `27,720`
- fetch attempts: `13,906`
- source snapshots: `27,720`
- runtime manifests covered: `43`
- runtime row lineage rows: `71,004`
- exact-authority lineage rows: `27,881`
- exact-authority unresolved rows: `0`
- unresolved runtime lineage rows: `0`
- runtime lineage status:
  - `matched_raw_document`: `34,924`
  - `matched_derived_structured_source_document`: `386`
  - `runtime_declared_source_document`: `35,694`
- source snapshot storage:
  - `api_response_cached`: `4,384`
  - `local_raw_snapshot_available`: `3,322`
  - `url_only_no_local_snapshot`: `19,966`
  - `missing_snapshot`: `48`

解释：exact facts 的来源血缘已经可以追溯；但大量 L2/L3 bounded context rows 仍只是 URL-only，说明后续 RD2/RD5/RD7 需要把重要 URL-only source 纳入 fetch/cache/replay gate，不能因为有 URL 就假装有可回放快照。

## 验证

- `python -m pytest tests/test_raw_source_provenance_store.py -q`：`3 passed`
- `python -m py_compile src/sec_agent/raw_source_provenance_store.py scripts/data_expansion/build_raw_source_provenance_store.py`：通过
- `python scripts/data_expansion/build_raw_source_provenance_store.py --max-hash-bytes 0`：通过并物化 RD1 provenance artifacts

## 后续

- RD2：建立 Silver Parser / Chunk / Table / Metric Ledger。重点把 parser version、input checksum、row count、drop reason、chunk/table/cell quality、runtime row lineage 和 rejection taxonomy 接起来。
- RD5/RD7：对 `url_only_no_local_snapshot` 做 source snapshot replay gate；重要 L2/L3 bounded source 需要缓存快照或绑定 run-time fetch attempt，不能只保留 URL。
- RD3：Gold Fact / Signal Mart 应直接消费 RD1 lineage id，而不是继续各自存散装 `source_url/raw_path` 字段。
