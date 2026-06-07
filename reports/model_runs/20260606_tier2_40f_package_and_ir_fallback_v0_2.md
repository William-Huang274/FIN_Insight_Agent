# Model Run: 20260606_tier2_40f_package_and_ir_fallback_v0_2

## Summary

- Purpose: Repair Tier2 SEC 40-F evidence coverage and harden non-SEC global-public company IR fallback.
- Status: staging diagnostic pass / not mainline.
- Run type: parser/index rebuild / retrieval smoke / downloader smoke.
- Timestamp: 2026-06-06.
- Environment: local Windows workspace, Python scripts, no LLM call.

## Changes

- 40-F annual package:
  - materialized Annual Information Form, audited financial statements, and MD&A exhibits into `40-F.annual_package.html`.
  - supports Canadian 40-F filename fallback such as `dex991/dex992/dex993`.
  - manifest now respects metadata `local_html_path` so downstream reads annual package instead of wrapper.
- 40-F splitter:
  - maps Canadian annual package sections to existing evidence semantics `1/1A/7/8`.
  - does not default to `7A`, because generic financial-instrument wording can consume large MD&A/financial statement sections.
- Global-public downloader:
  - added explicit `--allow-company-ir-fallback`.
  - annual-like reports require annual/business/integrated/securities report terms.
  - no-candidate branch writes metadata so stale wrong downloads do not look current.

## Outputs

- Tier2 SEC v0.2 summary: `data/manifests/tier2_supply_chain_sec_annual_staging_assets_summary_v0_2.json`
- Chunk audit: `eval/sec_cases/outputs/chunk_quality_audit/20260606_tier2_supply_chain_sec_annual_chunk_quality_v0_2/chunk_quality_summary.json`
- Samsung fallback smoke summary: `data/manifests/tier2_global_public_disclosure_samsung_ir_fallback_smoke_summary_v0_3.json`

## Results

- 40-F package materialization:
  - CCJ / TECK 2023-2025 six 40-F filings materialized.
  - 40-F zero-chunk filings: `6 -> 0`.
  - 40-F chunks: `2435`.
- Rebuilt Tier2 SEC staging:
  - chunks/evidence: `30600`
  - tables: `48977`
  - metrics: `421828`
  - claims: `240694`
  - SQLite FTS records: `711499`
  - ledger facts: `392015`
  - chunk quality audit: `pass`
- Retrieval smoke:
  - CCJ 40-F BM25 returns business evidence about nuclear fuel cycle, customers, and Westinghouse.
  - TECK / ARM ledger revenue rows return currency amount rows.
  - CCJ revenue ledger can still rank percent rows above amount rows, so currency/value-role ranking remains a gap.
- Samsung IR fallback smoke:
  - v0.1 selected `2023_Half_Interim_Report.pdf`, which was wrong.
  - after scoring repair, v0.3 rejects interim PDF and records `no_matching_document_candidate`.

## Gates

- `python -m pytest tests\test_sec_40f_annual_package.py tests\test_sec_20f_section_splitter.py -q`: `6 passed`
- `python -m pytest tests\test_global_public_disclosure_download_tasks.py -q`: `10 passed`
- `python -m compileall src\connectors\sec_edgar_connector.py src\connectors\sec_filing_manifest.py src\ingestion\section_splitter.py scripts\data_expansion\download_global_public_disclosures.py`: pass
- chunk quality audit: pass

## Interpretation

The Tier2 SEC annual shard is now materially better for Canadian 40-F issuers and can support staging retrieval for CCJ / TECK. It is still not ready for mainline promotion because global-public non-SEC parser/indexing is not built and exact-value ledger ranking needs source/form-aware currency-value preference.

## Safety Notes

- No API key, SSH password, private token, raw LLM response, or cloud credential was saved.
- Raw SEC files, non-SEC PDFs, local indexes, and eval outputs remain private/generated artifacts and should not be committed to a public repository.
