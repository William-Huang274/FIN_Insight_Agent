# 241 Tier 1 S&P 500 美国年报 Staging 资产

## Prompt

用户要求先下载美国年报，因为美国 SEC 年报处理规则已经稳定；下载完成后先给 S&P 500 做索引、chunk、数据库、Milvus，并给非美年报后续追加留出空间，避免非美下载后重新做 SEC 全量索引、chunk 和指标表格抽取。

## Reasoning And Decision

- 本轮只把 Tier 1 美国 10-K 放进 staging，不覆盖现有主线索引。
- 非美公开披露会作为后续 shard 追加，不能触发 SEC 年报重新 chunk。
- 旧 ObjectBM25 全量构建器会把 528 万结构化对象 token corpus 全部放进内存，不适合这批数据；本轮把结构化对象检索主后端切到 SQLite FTS，当前 `ObjectBM25Retriever` 已支持 `records.sqlite`。
- exact-value ledger 暴露了写入瓶颈：逐批 autocommit 太慢，单个大事务又会 OOM。已把 `LedgerStoreWriter` 改成分段事务，默认每 5 万行 commit，并关闭 DuckDB insertion-order preservation。
- full exact-value ledger 的主要瓶颈确认是脚本写入方式：旧路径用 Python `executemany` 批量插入 DuckDB，几百万行时非常慢且容易 OOM；新增 `csv_copy` 写入模式后，先写 TSV staging，再用 DuckDB `COPY` bulk load。
- 本地全量 metrics+tables ledger 在当前 RAM 下仍会 OOM；本轮先落 core exact-value ledger，覆盖 banking、capex、provision、revenue、margin、cash flow、R&D、云/数据中心/广告/半导体等核心 hard-number families。
- Milvus 只建 evidence semantic typed vectors，不向量化 528 万结构化对象；结构化对象仍由 SQLite FTS / runtime ledger 负责。

## Work Completed

- 新增 SEC 年报下载配置生成器：
  - `scripts/data_expansion/build_sec_annual_download_config.py`
  - 生成 `configs/data_sources/tier1_sp500_us_annual_10k_fy2023_2025.yaml`
  - 生成 `data/manifests/tier1_sp500_us_annual_download_config_summary_v0_1.json`
- 新增 staging dataset registry：
  - `configs/data_sources/layered_staging_datasets_v0_1.yaml`
  - 明确 SEC active shard 和非美公开披露 reserved shard。
  - 明确不允许 staging index 覆盖主线 index。
- 扩展 evidence schema：
  - `business_report`
  - `annual_securities_report`
  - `integrated_report`
  - `primary_global_public_disclosure`
- 把 `scripts/data_retrieval/build_evidence_store.py` 改成 streaming 构建，避免把 16 万 chunks 一次性读入内存。
- 构建本地 staging 资产：
  - SEC 10-K 原始下载：`1500` 份成功。
  - 下载缺口：`15` 条，主要是新上市/拆分/新 ticker 或 fiscal-year 口径不可得。
  - Manifest：`1500` records。
  - Chunks：`161455` records。
  - EvidenceObject：`161455` records。
  - Structured objects：`166025` tables、`3896142` metrics、`1223646` claims。
  - Evidence BM25：`161455` records。
  - Structured object SQLite FTS：`5285809` records。
- 云端执行：
  - 把必要代码、evidence、metrics、tables 打成 zstd 包，8.18GB 输入压缩成约 0.35GB。
  - 上传到 `/root/autodl-tmp/fin_agent_sp500_stage`。
  - 云端依赖安装在 base conda，pip cache 放 `/root/autodl-tmp/pip_cache`。
  - Milvus build-only smoke 通过，BGE-M3 走 CUDA。
  - 全量 Milvus evidence semantic build 通过，typed vectors 总量 `460988`，不包含结构化对象向量。
  - Milvus query smoke 通过：`NVIDIA data center revenue AI infrastructure supply constraints` 返回 NVDA Item 1A / Item 7 evidence，top hit 为 `paraphrase_context`。
- exact-value ledger：
  - 云端全量 ledger 已启动，最后可观测进度为 `3750404` 源对象、`2736208` rows extracted、`2730000` rows written；随后 SSH banner 连续失败，暂不能确认是否完成。
  - 本地全量 ledger 用修复后的 writer 重跑，仍在 DuckDB insert 阶段触发 RAM OOM。
  - 本地 core ledger 已完成：扫描 `4062164` 个 metrics+tables 源对象，生成 `908586` 条核心数值事实，用时 `1198.751` 秒，DuckDB 大小约 `175.26MB`。
  - core ledger query smoke 通过：MSFT capex top row 为 `Additions to property and equipment`，JPM provision top row 为 `Provision for credit losses`，NVDA revenue top row 为 `Compute & Networking`。
  - 云端 full ledger 已完成：扫描 `4062160` 个 metrics+tables 源对象，生成 `4810839` 条数值事实，用时 `240.58` 秒，DuckDB 大小约 `990.76MB`。
  - full ledger query smoke 通过：MSFT capex、JPM provision、NVDA revenue 均返回可用 hard-number rows。
  - 性能对比：旧 `duckdb_executemany` 路径 2 小时后只写到约 `2730000` rows 且未完成；新 `csv_copy` 路径约 4 分钟完成全量 `4810839` rows。

## Result And Evidence

Tracked summary：

- `data/manifests/tier1_sp500_us_annual_staging_assets_summary_v0_1.json`

本地资产：

- raw private：`data/raw_private/sec_tier1_sp500_annual`
- manifest：`data/staging/sec_tier1_sp500_annual/manifests/tier1_sp500_us_annual_10k_manifest_fy2023_2025_v0_1.jsonl`
- chunks：`data/staging/sec_tier1_sp500_annual/chunks/tier1_sp500_us_annual_10k_chunks_fy2023_2025_v0_1.jsonl`
- evidence：`data/staging/sec_tier1_sp500_annual/evidence/tier1_sp500_us_annual_10k_evidence_fy2023_2025_v0_1.jsonl`
- structured objects：`data/staging/sec_tier1_sp500_annual/structured_objects`
- evidence BM25：`data/indexes/staging/bm25/tier1_sp500_us_annual_10k_fy2023_2025_v0_1`
- object SQLite FTS：`data/indexes/staging/sqlite_fts/tier1_sp500_us_annual_10k_objects_fy2023_2025_v0_1`

下载缺口：

- BLK 2023
- FDXF 2023 / 2024 / 2025
- GEV 2023
- KR 2023
- PSKY 2023 / 2024
- Q 2023 / 2024
- SNDK 2023 / 2024
- SOLV 2023
- SW 2023
- CRWD 2025

本地验证：

```powershell
python -m pytest tests\test_sec_annual_download_config.py tests\test_layered_staging_dataset_registry.py tests\test_evidence_schema_global_public.py tests\test_build_evidence_store_streaming.py -q
python -m pytest tests\test_sec_agent_ledger_store.py -q
python -m compileall scripts\data_expansion\build_sec_annual_download_config.py scripts\data_retrieval\build_evidence_store.py src\evidence\schema.py src\sec_agent\ledger_store.py
```

结果：

- staging / schema / evidence store targeted tests：pass。
- ledger store tests：`8 passed`。
- compileall：pass。

## Follow-Up

- full ledger 已在云端完成；如需本地直接运行 full exact lookup，可后续拉回约 `990.76MB` DuckDB，或在云端 full-chain/eval 使用远端路径。
- 对 runtime ledger 不再使用 Python `executemany` 全量写；全量构建应使用 `csv_copy` 或后续 shard/partition DuckDB / Parquet 批量载入。
- 非美公开披露进入 parser/chunk 前，不触发 SEC staging 重新 chunk。

## Safety Notes

- 没有把云端 SSH 密码、API key 或私有 token 写入文件。
- raw、staging、index、log 产物不进入 Git。
- Milvus 和 ledger 当前仍为 staging-only，不能提升为主线向量库。
- Milvus DB 当前保留在云端 staging 路径；本地下载速度偏低，暂不拉回 3.6GB DB，只把 summary 和 query smoke 结果写入 tracked summary。
- core ledger 是本地可用 exact-value staging artifact；full ledger 是云端可用 exact-value staging artifact。评测和运行时需要显式引用对应路径，避免误把 core ledger 当成全量 ledger。
