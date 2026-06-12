# 260 公开数据源 normalized collector smoke

## Prompt

用户确认可以继续按 P0-P3 数据接入推进。上一轮已完成 key 本地配置、P1/P2/optional key live smoke，本轮继续把通过 smoke 的公开源落成可复用 normalized collector 合同和小批样例输出。

## Decision

本轮不升级 Agent Graph / Skill，也不把公开源直接提升为主线向量库或生产证据。

执行边界：

- 新 collector 输出 `normalized_records` 和 `evidence_rows`，作为后续 agent data-view 接入候选。
- 小批 normalized 输出写入 ignored 的 `data/processed_private/public_sources/`。
- 可提交 manifest 只保留 summary 指针和统计，不保存原始 payload 或密钥。
- 所有记录带 `claim_scope`、`claim_boundary`、`source_policy`，防止宏观/监管/实体映射数据被误用成公司级收入、销量或盈利证据。

## Work Completed

- 新增 `scripts/data_expansion/download_public_source_normalized_snapshots.py`。
- 新增 `tests/test_public_source_normalized_snapshot.py`。
- collector 支持两条线：
  - `macro_industry`：FRED API、BLS、BEA、Census、EIA、FDIC。
  - `identity_product_disclosure`：SEC Submissions、DART company reference、GLEIF、OpenFIGI、ClinicalTrials.gov、openFDA、NHTSA vPIC。
- 支持 query param、JSON body、HTTP header 三种 key 注入；输出 URL 和错误消息做 key 脱敏。
- 生成真实小批 snapshot summary：
  - `data/manifests/public_source_normalized_snapshot_summary_v0_1.json`
- 生成 ignored normalized 产物：
  - `data/processed_private/public_sources/public_source_normalized_smoke_v0_1/normalized_records.jsonl`
  - `data/processed_private/public_sources/public_source_normalized_smoke_v0_1/evidence_rows.jsonl`
  - `data/processed_private/public_sources/public_source_normalized_smoke_v0_1/failures.jsonl`
  - `data/processed_private/public_sources/public_source_normalized_smoke_v0_1/metadata.json`

## Results

真实 normalized smoke：

- selected sources：`13`
- successful sources：`13`
- failed sources：`0`
- normalized records：`118`
- evidence rows：`13`
- collector line counts：
  - `macro_industry`: `68`
  - `identity_product_disclosure`: `50`
- source family counts：
  - `macro_industry_indicator`: `68`
  - `sec_submissions_metadata`: `25`
  - `official_product_status`: `18`
  - `relationship_edge`: `6`
  - `global_public_annual_report`: `1`
- record type counts：
  - `macro_time_series_observation`: `37`
  - `macro_table_observation`: `25`
  - `filing_metadata_record`: `25`
  - `clinical_trial_status_record`: `5`
  - `fda_product_status_record`: `5`
  - `institution_reference_record`: `5`
  - `legal_entity_identifier_record`: `5`
  - `vehicle_model_identity_record`: `8`
  - `macro_cross_section_observation`: `1`
  - `primary_disclosure_company_reference_record`: `1`
  - `security_identifier_mapping_record`: `1`

Claim boundary remains unchanged:

- macro/industry records are context only.
- identity/product/disclosure records can support identifiers, legal-entity mappings, regulatory/product status, or primary-disclosure metadata.
- Company-level product sales, revenue, deliveries, subscribers, ARPU, backlog, or orders still require company-reported product operating metrics.

## Validation

- `python -m py_compile scripts/data_expansion/download_public_source_normalized_snapshots.py` -> pass
- `python scripts/data_expansion/download_public_source_normalized_snapshots.py --snapshot-id public_source_normalized_smoke_v0_1 --manifest-output data/manifests/public_source_normalized_snapshot_summary_v0_1.json --allow-source-failures --timeout-s 30 --max-records-per-source 25` -> pass, `13/13` sources
- `python -m pytest tests/test_public_source_normalized_snapshot.py tests/test_public_source_access_plan.py tests/test_industry_source_snapshot.py tests/test_market_industry_expansion_manifests.py` -> `10 passed`
- `git check-ignore -v data/processed_private/public_sources/public_source_normalized_smoke_v0_1/normalized_records.jsonl .env` -> both ignored
- `.env` value scan over changed code/docs/manifests and the normalized smoke output -> `NO_SECRET_VALUE_HITS`
- `git diff --check` -> pass

## Follow-up

- Add a small adapter that loads `evidence_rows.jsonl` into the existing source inventory / Evidence Fusion Selector behind a feature flag.
- Add `company_product_operating_metric` ontology/parser next, because public regulatory/product APIs cannot answer actual company product sales questions.
- Add EDINET smoke only after `EDINET_API_KEY` is available.
- Keep commercial APIs and consensus feeds deferred under the current no-paid-API policy.
