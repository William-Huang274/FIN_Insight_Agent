# Model Run: 20260606_tier2_supply_chain_sec_annual_staging_index_ledger_v0_1

## Summary

- Purpose: Build Tier2 supply-chain SEC annual primary-disclosure staging assets.
- Status: accepted staging diagnostic / not mainline.
- Run type: index build / ledger build / retrieval asset smoke.
- Timestamp: 2026-06-06.
- Environment: local Windows workspace, Python scripts, no LLM call.

## Code And Command

- SEC config:
  - `python scripts\data_expansion\build_sec_annual_download_config.py --manifest data\manifests\tier2_supply_chain_supplement_manifest.jsonl --output configs\data_sources\tier2_supply_chain_sec_annual_fy2023_2025.yaml --summary-output data\manifests\tier2_supply_chain_sec_annual_download_config_summary_v0_1.json --years 2023,2024,2025 --form-types 10-K,20-F,40-F --dataset-id tier2_supply_chain_sec_annual_v0_1 --universe-tier tier2_supply_chain_supplement`
- SEC download:
  - `python scripts\data_sec\download_sec_filings.py --config configs/data_sources/tier2_supply_chain_sec_annual_fy2023_2025.yaml --cache-dir data/raw_private/sec_tier2_supply_chain_annual --allow-missing --rate-limit 2.0`
- Chunk/evidence/structured:
  - `python scripts\data_sec\build_sec_chunks.py --manifest data/staging/sec_tier2_supply_chain_annual/manifests/tier2_supply_chain_sec_annual_manifest_fy2023_2025_v0_1.jsonl --output data/staging/sec_tier2_supply_chain_annual/chunks/tier2_supply_chain_sec_annual_chunks_fy2023_2025_v0_1.jsonl --workers 4`
  - `python scripts\data_retrieval\build_evidence_store.py --chunks data/staging/sec_tier2_supply_chain_annual/chunks/tier2_supply_chain_sec_annual_chunks_fy2023_2025_v0_1.jsonl --output data/staging/sec_tier2_supply_chain_annual/evidence/tier2_supply_chain_sec_annual_evidence_fy2023_2025_v0_1.jsonl`
  - `python scripts\data_retrieval\build_structured_objects.py --evidence data/staging/sec_tier2_supply_chain_annual/evidence/tier2_supply_chain_sec_annual_evidence_fy2023_2025_v0_1.jsonl --output-dir data/staging/sec_tier2_supply_chain_annual/structured_objects --prefix tier2_supply_chain_sec_annual_fy2023_2025_v0_1 --workers 4`
- Index / ledger:
  - `python scripts\data_retrieval\build_bm25_index.py --evidence data/staging/sec_tier2_supply_chain_annual/evidence/tier2_supply_chain_sec_annual_evidence_fy2023_2025_v0_1.jsonl --output-dir data/indexes/staging/bm25/tier2_supply_chain_sec_annual_fy2023_2025_v0_1 --workers 4`
  - `python scripts\data_retrieval\build_object_sqlite_fts_index.py --structured-dir data/staging/sec_tier2_supply_chain_annual/structured_objects --prefix tier2_supply_chain_sec_annual_fy2023_2025_v0_1 --output-dir data/indexes/staging/sqlite_fts/tier2_supply_chain_sec_annual_objects_fy2023_2025_v0_1 --workers 4 --skip-fts-optimize`
  - `python scripts\ledger\10_build_lightweight_ledger_store.py --structured-dir data/staging/sec_tier2_supply_chain_annual/structured_objects --prefix tier2_supply_chain_sec_annual_fy2023_2025_v0_1 --output-path data/indexes/staging/ledger/tier2_supply_chain_sec_annual_fy2023_2025_v0_1_ledger.duckdb --workers 4 --write-mode csv_copy`

## Inputs

- Universe manifest: `data/manifests/tier2_supply_chain_supplement_manifest.jsonl`
- Companies: `83` SEC-download eligible Tier2 companies.
- Forms: company-level annual SEC forms from `target_forms`, restricted to `10-K` / `20-F` / `40-F`.
- Years: `2023`、`2024`、`2025`.

## Outputs

- Download config: `configs/data_sources/tier2_supply_chain_sec_annual_fy2023_2025.yaml`
- Download summary: `data/manifests/tier2_supply_chain_sec_annual_download_config_summary_v0_1.json`
- Staging summary: `data/manifests/tier2_supply_chain_sec_annual_staging_assets_summary_v0_1.json`
- Filing manifest: `data/staging/sec_tier2_supply_chain_annual/manifests/tier2_supply_chain_sec_annual_manifest_fy2023_2025_v0_1.jsonl`
- Chunks: `data/staging/sec_tier2_supply_chain_annual/chunks/tier2_supply_chain_sec_annual_chunks_fy2023_2025_v0_1.jsonl`
- Evidence: `data/staging/sec_tier2_supply_chain_annual/evidence/tier2_supply_chain_sec_annual_evidence_fy2023_2025_v0_1.jsonl`
- Structured objects: `data/staging/sec_tier2_supply_chain_annual/structured_objects`
- BM25 index: `data/indexes/staging/bm25/tier2_supply_chain_sec_annual_fy2023_2025_v0_1`
- SQLite FTS object index: `data/indexes/staging/sqlite_fts/tier2_supply_chain_sec_annual_objects_fy2023_2025_v0_1`
- Exact-value ledger: `data/indexes/staging/ledger/tier2_supply_chain_sec_annual_fy2023_2025_v0_1_ledger.duckdb`
- Chunk audit: `eval/sec_cases/outputs/chunk_quality_audit/20260606_tier2_supply_chain_sec_annual_chunk_quality_v0_1/chunk_quality_summary.json`

## Results

- SEC download: `226/249` filings downloaded.
- Downloaded forms: `10-K=143`、`20-F=77`、`40-F=6`.
- Download gaps: `23`.
- Chunks/evidence: `28165`.
- 20-F chunks after parser fix: `13316`.
- Remaining zero-chunk filings: `6`, all `40-F` wrapper files for `CCJ` and `TECK`.
- Structured objects: `43736` tables, `396565` metrics, `231091` claims.
- BM25 evidence index: `28165` records.
- SQLite FTS object index: `671392` records.
- Exact-value ledger: `373643` facts, elapsed about `27.1` sec using `csv_copy`.
- Chunk quality audit: `pass`.

## Interpretation

The Tier2 SEC annual shard is usable as staging evidence for 10-K and 20-F issuers. It is not ready for mainline promotion because 40-F exhibits are not materialized and some 20-F exact-value rows need ranking/currency-role tuning before they should drive final memo claims.

## Safety Notes

- No API key, SSH password, private token, raw LLM response, or cloud credential was saved.
- Raw SEC files and local indexes remain private/generated artifacts and should not be committed to a public repository.
