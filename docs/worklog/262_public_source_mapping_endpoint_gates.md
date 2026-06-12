# 262 公开数据源 mapping / endpoint gates

## Prompt

用户要求不要停在 full audit 结论，直接做 mapping、endpoint gates，把需要用的数据下载并处理好，然后再报告缺口。

## Decision

本轮按当前 Tier1+Tier2 `603` 家 universe 做 target-universe scoped 下载和处理，不做 GLEIF、ClinicalTrials.gov、openFDA 等全网全库下载。原因：

- 后续 agent runtime 的目标是当前 603 家投研 universe，不是公共源全库检索。
- 全库下载体量大、可复现性差，且会引入大量当前 agent 不会消费的实体。
- source gap 应基于目标 universe、source family 和 claim boundary 报告。

raw / bulk / processed 数据只写入 ignored `data/processed_private/public_sources/public_source_mapping_endpoint_gate_v0_1/`；tracked manifest 只保留统计、路径和缺口摘要。

## Work Completed

- 新增 `scripts/data_expansion/build_public_source_mapping_endpoint_gates.py`。
- 新增 `tests/test_public_source_mapping_endpoint_gates.py`。
- 读取 `data/manifests/tier1_tier2_market_universe_v0_1.csv` 和 `data/manifests/tier1_plus_tier2_supply_chain_manifest.jsonl`，生成 603 家 universe entity rows。
- 对以下源执行 target-universe mapping / endpoint gates：
  - `sec_universe_identity`
  - `openfigi_api`
  - `gleif_api`
  - `fdic_bankfind_api`
  - `clinicaltrials_api`
  - `openfda_api`
  - `nhtsa_vpic_api`
  - `census_data_api`
  - `eia_open_data`
  - `kr_dart_openapi`
- 生成 tracked gate manifest：
  - `data/manifests/public_source_mapping_endpoint_gate_v0_1.jsonl`
  - `data/manifests/public_source_mapping_endpoint_gate_summary_v0_1.json`
- 生成 ignored processed artifacts：
  - `endpoint_records.jsonl`
  - `mapping_candidates.jsonl`
  - `source_gaps.jsonl`
  - `universe_entities.jsonl`
  - `metadata.json`

## Result

总体：

- universe companies：`603`
- source gates：`10`
- status counts：`5 pass`、`5 partial`
- endpoint records：`127,712`
- mapping candidates：`1,219`
- source gaps：`213`
- agent promotion：`false`

已下载和处理：

- SEC identity：`588` 个 SEC eligible issuers CIK 映射，`0` gap。
- OpenFIGI：`15` 个 non-US/local listing jobs 中 `14` 个映射成功，`1` gap（`1211.HK` BYD local listing 未返回 FIGI）。
- GLEIF：target-universe legal-name query 生成 `1,380` endpoint records，`520` 个 LEI candidate mappings，`83` gaps。
- FDIC BankFind：下载 `4,276` 个 active institutions，生成 `11` 个银行/金融机构 subsidiary/institution candidates，`65` gaps。
- ClinicalTrials.gov：healthcare target `68` 家，下载 `1,946` study records，`60` 家有 sponsor-query candidate，`8` gaps。
- openFDA：healthcare target `68` 家，下载 `402` drug/drugsfda sponsor records，`15` 家有 sponsor-query candidate，`53` gaps。
- NHTSA vPIC：auto target `11` 家，下载 `247` model identity records，`8` 家有 make candidate，`3` gaps。
- Census ACS：下载 2021/2022/2023 ACS5 US-level `B01001_001E` records，`0` gap。
- EIA：下载 `1,000` records，覆盖 total-energy 和 electricity retail-sales 两条 endpoint gate，`0` endpoint gap；仍是 route/entity mapping partial。
- DART：下载 DART corp code 全表 `118,294` rows，并为 `000660.KS`、`005930.KS`、`373220.KS` 映射 corp_code；下载近期 filing metadata `150` rows。

## Key Gaps

- GLEIF：`83` gaps，其中 `40` no LEI candidate、`43` low-confidence candidate；需要 alias / legal-name override，不能用低置信候选直接做 issuer mapping。
- FDIC：`65` financial issuers 未映射到 active FDIC institution；已映射的 `11` 条也只是 subsidiary/institution candidate，不是上市 issuer 级事实。
- ClinicalTrials.gov：`8` healthcare issuers sponsor query 无结果；已有 `60` 家仍需 sponsor/product/condition resolver。
- openFDA：`53` healthcare issuers sponsor alias 无 drug/drugsfda 结果；openFDA 只覆盖监管/产品状态，不覆盖销售或商业采用。
- NHTSA：`3` auto targets 无 make/model match；已修正 make-name token gate，避免 `NIO`/`LI` 这类 fuzzy false positive。
- EIA：endpoint 已可下载，但还缺 company/asset/route allowlist，不能推导公司收入或产品销量。
- DART：corp_code 和 filing metadata 已可用，但仍缺 document/package downloader/parser，不能把 DART filing metadata 升级为可引用主披露正文证据。

## Validation

- `python -m py_compile scripts/data_expansion/build_public_source_mapping_endpoint_gates.py` -> pass
- `python -m pytest tests/test_public_source_mapping_endpoint_gates.py` -> `5 passed`
- `python scripts/data_expansion/build_public_source_mapping_endpoint_gates.py --allow-source-failures --timeout-s 30 --sleep-s 0.02 --max-records-per-company 50` -> pass with gaps

## Follow-up

- Add resolver confidence thresholds before runtime use:
  - `high`: direct CIK / FIGI / DART stock-code match.
  - `medium`: sponsor/make/subsidiary candidate, must stay source-specific context.
  - `low/unmatched`: source gap only.
- Add source-specific adapters for source inventory that read only approved gate rows.
- Add manual alias overrides for high-value GLEIF, openFDA, ClinicalTrials.gov, and NHTSA misses.
- Build DART document/package parser before using Korean filings as primary disclosure evidence.
- Keep runtime promotion blocked until source-boundary adapters enforce these decisions.
