# Model Run: 20260606_tier1_sp500_us_annual_staging_index_ledger_milvus_v0_1

## Summary

- Purpose: Build Tier 1 S&P 500 plus current US 10-K staging retrieval assets without overwriting mainline indexes.
- Status: accepted staging diagnostic; not promoted to mainline.
- Run type: index build / embedding build / ledger build.
- Timestamp: 2026-06-05 to 2026-06-06 Asia/Shanghai.
- Environment: local Windows D drive for SEC download/chunk/BM25/SQLite FTS/core ledger; cloud RTX 4090 for BGE-M3 Milvus evidence vectors.

## Code And Command

- Entry points:
  - `scripts/data_expansion/build_sec_annual_download_config.py`
  - `scripts/data_retrieval/build_evidence_store.py`
  - `scripts/ledger/10_build_lightweight_ledger_store.py`
  - `scripts/eval_retrieval/eval_milvus_retrieval_ab.py`
- Configs:
  - `configs/data_sources/tier1_sp500_us_annual_10k_fy2023_2025.yaml`
  - `configs/data_sources/layered_staging_datasets_v0_1.yaml`
- Dirty files: this branch contains staged prior data-expansion work plus current ledger/Milvus staging updates.
- Seeds: deterministic build; no random training seed.

## Inputs

- Universe: 505 SEC-download eligible companies from S&P 500 plus retained current-only companies.
- Requested filings: 2023-2025 Form 10-K, 1515 tasks.
- Download result: 1500 filings downloaded, 15 missing/error rows recorded.
- Structured source:
  - tables: 166025
  - metrics: 3896142
  - claims: 1223646

## Outputs

- Chunks: `data/staging/sec_tier1_sp500_annual/chunks/tier1_sp500_us_annual_10k_chunks_fy2023_2025_v0_1.jsonl`, 161455 rows.
- Evidence: `data/staging/sec_tier1_sp500_annual/evidence/tier1_sp500_us_annual_10k_evidence_fy2023_2025_v0_1.jsonl`, 161455 rows.
- Evidence BM25: `data/indexes/staging/bm25/tier1_sp500_us_annual_10k_fy2023_2025_v0_1`, 161455 records.
- Structured object SQLite FTS: `data/indexes/staging/sqlite_fts/tier1_sp500_us_annual_10k_objects_fy2023_2025_v0_1`, 5285809 records.
- Milvus evidence semantic DB: cloud staging path under `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/indexes/staging/milvus`.
- Local core ledger: `data/indexes/staging/ledger/tier1_sp500_us_annual_10k_fy2023_2025_v0_1_core_ledger.duckdb`, 908586 facts, 175.26MB.
- Cloud full ledger: `/root/autodl-tmp/fin_agent_sp500_stage/workspace/data/indexes/staging/ledger/tier1_sp500_us_annual_10k_fy2023_2025_v0_1_full_ledger.duckdb`, 4810839 facts, 990.76MB.
- Tracked summary: `data/manifests/tier1_sp500_us_annual_staging_assets_summary_v0_1.json`.

## Results

- Milvus build: pass.
  - BGE-M3 device: CUDA.
  - Collection rows: 460988.
  - Vector kinds: narrative 161455, paraphrase 152959, relationship 76331, table 70243.
  - Query smoke: NVDA AI infrastructure query returned NVDA Item 1A / Item 7 rows.
- Core ledger build: pass.
  - Source records scanned: 4062164 metrics+tables.
  - Ledger facts: 908586.
  - Elapsed: 1198.751 sec.
  - Query smoke: MSFT capex, JPM credit provision, and NVDA revenue all returned usable hard-number rows.
- Full ledger: pass on cloud.
  - Source records scanned: 4062160 metrics+tables.
  - Ledger facts: 4810839.
  - Elapsed: 240.58 sec.
  - Query smoke: MSFT capex, JPM credit provision, and NVDA revenue all returned usable hard-number rows.
  - Root cause of the previous 1-2 hour run: the old path used Python `executemany` into DuckDB. The replacement `csv_copy` path writes TSV staging rows and lets DuckDB bulk-load them with `COPY`.

## Decision

- Promote as staging-only assets for diagnostic retrieval and next relationship/data-source work.
- Use the local core ledger for local exact-value route smoke and the cloud full ledger for full S&P 500 hard-number tests.
- Treat `csv_copy` as the accepted full-ledger build mode; do not use the old `duckdb_executemany` path for multi-million-row full ledger builds.
- Do not pull 3.6GB Milvus DB locally unless needed; record remote path and summary instead.

## Verification

- `python -m pytest tests\test_sec_agent_ledger_store.py tests\test_lightweight_ledger_builder.py -q` passed with 13 tests.
- `python -m compileall src\sec_agent\ledger_store.py scripts\ledger\10_build_lightweight_ledger_store.py` passed.
- Milvus query smoke and core ledger query smoke passed.

## Safety Notes

- No API key, SSH password, or private token was written to this report.
- Raw, staging, index, and log artifacts remain outside Git by default.
