# 258 公开数据源 P0-P3 接入骨架

## Prompt

用户要求先做 P0-P3 数据接入；需要人工注册的 key 由 Codex 明确告知。

## Decision

本轮做“registry 驱动的接入骨架”，不把数据直接接入主线 RAG/vector/agent graph。

阶段边界：

- P0：校验 `configs/data_sources/public_source_coverage_v0_1.yaml`，生成 access plan、P2 key gap 和 P3 validation tasks。
- P1：对 no-key / no-key-limited 来源做 bounded live probe，只保存 normalized smoke metadata，不保存 raw payload。
- P2：检测免费 key 环境变量，缺 key 时写入 auth gap，不失败、不写密钥。
- P3：生成 official portal / endpoint validation tasks，不直接做 profile-specific scraper。

## Work Completed

- 新增 `scripts/data_expansion/build_public_source_access_plan.py`。
- 新增 `scripts/data_expansion/probe_public_source_access.py`。
- 新增 `tests/test_public_source_access_plan.py`。
- 更新 `configs/data_sources/public_source_coverage_v0_1.yaml`，将 PatentsView 调整为 USPTO Open Data Portal 迁移后的 endpoint validation pending。
- 生成 P0-P3 产物：
  - `data/manifests/public_source_access_plan_v0_1.jsonl`
  - `data/manifests/public_source_access_plan_summary_v0_1.json`
  - `data/manifests/public_source_access_probe_v0_1.jsonl`
  - `data/manifests/public_source_access_probe_summary_v0_1.json`
  - `data/manifests/public_source_portal_validation_tasks_v0_1.jsonl`

## Results

P0 registry validation:

- source count：`32`
- unique source ids：`32`
- registry errors：`0`
- warnings：`0`
- phase counts：P1 `20`，P2 `6`，P3 `5`，deferred `1`

P1 live probe:

- candidate count：`8`
- passed：`8/8`
- passed sources：
  - `sec_edgar_apis`
  - `fred_graph_csv`
  - `fdic_bankfind_api`
  - `clinicaltrials_api`
  - `openfda_api`
  - `nhtsa_vpic_api`
  - `gleif_api`
  - `openalex_api`

P2 key requirements:

- Required but currently missing:
  - `BEA_API_KEY`
  - `CENSUS_API_KEY`
  - `DART_API_KEY`
  - `EDINET_API_KEY`
  - `EIA_API_KEY`
  - `FRED_API_KEY`
- Optional enhancement keys currently absent:
  - `BLS_API_KEY`
  - `OPENFDA_API_KEY`
  - `OPENFIGI_API_KEY`

P3 validation tasks:

- `cninfo_portal`
- `hkexnews_portal`
- `patentsview_api`
- `tw_mops_portal`
- `usitc_dataweb_and_trade`

## Validation

- `python -m pytest tests/test_public_source_access_plan.py` -> `3 passed`
- `python scripts/data_expansion/build_public_source_access_plan.py` -> pass
- `python scripts/data_expansion/probe_public_source_access.py --allow-failures --timeout-s 25` -> pass, `8/8`

No model run, no full-chain eval, and no raw private data promotion happened in this iteration.

## Follow-up

- Ask user to register/configure required free keys before P2 live collector work.
- Implement the first real normalized collectors for P1 passed sources, starting with FDIC, ClinicalTrials.gov/openFDA, GLEIF/OpenFIGI, and product operating metrics from company filings.
- Run P3 validation source-by-source, starting with HKEXnews or CNINFO only after target issuer examples are selected.
- Keep commercial market/consensus data deferred under the current no-paid-API policy.
