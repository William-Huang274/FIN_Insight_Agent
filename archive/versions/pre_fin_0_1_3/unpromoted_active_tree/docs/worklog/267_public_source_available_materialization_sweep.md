# 267 公开可得源物化扫尾与结构化首选路径

## Prompt

用户明确要求：除 `jp_edinet_api` 目前无法 issue/激活 key、`commercial_market_data_and_consensus` 按 no-commercial 策略延后外，其他公开可得源如果可用都要物化；`sec_financial_statement_data_sets` 和 `FRED` 如果比从文档抽取更好用，后续应走结构化数据路径，不再默认从文档里抽。

## Decision

- 把“公开可得”拆成三类物化：normalized snapshot、extended bulk/artifact、已有非美 cleaned-text staging。
- `SEC Financial Statement Data Sets` 作为结构化财务事实候选权威路径落地 bulk zip，后续需要 bulk parser 与 CompanyFacts/filing citation parity gate；通过后可优先于文档抽取做标准化数值事实。
- `FRED API` 作为 key-backed preferred macro path；`fred_graph_csv` 保留为 no-key fallback。
- `OpenAlex`、`Wikidata`、`GDELT`、`Common Crawl`、`Yahoo chart`、`PatentsView/USPTO ODP` 都做 bounded materialization，但仍是 lead/context/resolver/provisional，不允许替代公司披露、监管事实或 commercial consensus。
- `PatentsView` 当前只物化 USPTO/PatentsView 迁移元数据；专利表/API 仍需 Open Data Portal endpoint validation。
- `Tesla` 官方产品页脚本请求返回 403；company product page sample 改为 Apple / NVIDIA / AMD 三个可复跑官方页面，Tesla 作为站点反爬缺口，不阻塞 source-level materialization。

## Work Completed

- 更新 `scripts/data_expansion/download_public_source_normalized_snapshots.py`：
  - 支持 `response_format: text`。
  - 新增 `yahoo_chart`、`openalex_api`、`wikidata`、`gdelt`、`common_crawl_index`、`patentsview_api` profiles。
  - 新增 market price、research work lead、alias candidate、event data index、crawl index metadata、patent data access metadata parsers。
- 更新 `scripts/data_expansion/download_public_source_extended_materialization.py`：
  - SEC FSD 和 13F bulk zip materializer 保持落到 Z 盘。
  - 产品页面抓取改用浏览器 UA，并把样本固定为 Apple iPhone、NVIDIA Blackwell、AMD Ryzen。
  - 产品运营指标 candidate table 和 ontology 保持 parser-gate pending。
- 更新 `scripts/data_expansion/build_public_source_access_plan.py`、`configs/data_sources/public_source_coverage_v0_1.yaml`、`configs/data_sources/public_source_information_strength_v0_1.yaml`：
  - 把新增公开可得源从 source-plan only 改成 bounded materialized / normalized snapshot gate pending。
  - 保留 lead-only、context-only、provisional-only 和 endpoint-validation 边界。
- 重建 manifests 和报告：
  - `data/manifests/public_source_access_plan_v0_1.jsonl`
  - `data/manifests/public_source_access_plan_summary_v0_1.json`
  - `data/manifests/public_source_normalized_snapshot_summary_v0_1.json`
  - `data/manifests/public_source_extended_materialization_v0_1.jsonl`
  - `data/manifests/public_source_extended_materialization_summary_v0_1.json`
  - `data/manifests/company_product_operating_metric_candidates_v0_1.jsonl`
  - `data/manifests/public_source_strength_materialization_matrix_v0_1.jsonl`
  - `data/manifests/public_source_strength_materialization_summary_v0_1.json`
  - `docs/internal/vnext_20260610/public_source_strength_materialization.zh-CN.md`

## Results

Normalized public-source snapshot `public_source_normalized_materialized_v0_3`：

- selected sources：`22`
- successful sources：`22`
- failed sources：`0`
- normalized records：`404`
- evidence rows：`22`
-新增/确认来源包括：`fred_api`、`fred_graph_csv`、`bls_public_api`、`bea_data_api`、`census_data_api`、`eia_open_data`、`fdic_bankfind_api`、`cms_public_data`、`usitc_dataweb_and_trade`、`yahoo_chart`、`openalex_api`、`wikidata`、`gdelt`、`common_crawl_index`、`patentsview_api`、`sec_edgar_apis`、`kr_dart_openapi`、`gleif_api`、`openfigi_api`、`clinicaltrials_api`、`openfda_api`、`nhtsa_vpic_api`。

Extended materialization：

- `sec_financial_statement_data_sets`：`85,259,424` bytes downloaded/inspected，`4,522,052` table rows counted。
- `sec_ownership_and_13f`：`99,411,274` bytes downloaded/inspected，`3,877,007` table rows counted。
- `company_product_pages`：`3` official product pages，`128,137` cleaned chars。
- `company_reported_product_operating_metrics`：`300` candidate rows，仍需 value/unit/period/product parser。

S5-S0 materialization summary：

- source count：`32`
- materialized source count：`30`
- remaining non-materialized/deferred：`jp_edinet_api` official API、`commercial_market_data_and_consensus`
- normalized snapshot records：`404`
- industry snapshot observations：`64,529`
- extended materialization records：`8,399,362`
- extended downloaded bytes：`184,670,698`
- SEC structured fact rows：`2,790,261`
- non-US cleaned text chars：`24,114,298`
- EDINET official gap rows：`30`

## Validation

- `python -m py_compile scripts\data_expansion\download_public_source_normalized_snapshots.py scripts\data_expansion\build_public_source_access_plan.py scripts\data_expansion\download_public_source_extended_materialization.py scripts\data_expansion\build_public_source_strength_materialization_report.py` -> pass
- `python -m pytest tests\test_public_source_normalized_snapshot.py tests\test_public_source_access_plan.py tests\test_public_source_extended_materialization.py tests\test_public_source_strength_materialization_report.py` -> `17 passed`
- Live normalized collector -> `22/22` sources pass, failures `0`
- Live extended materializer -> `4/4` source groups pass, failures `0`

## Follow-up

- Build SEC FSD bulk parser and parity gate against accepted CompanyFacts/filing citation pipeline; parity pass 后把标准化数值事实优先改走 SEC FSD / CompanyFacts，而不是文档抽取。
- Build FRED series allowlist/metadata adapter；宏观时间序列默认走 FRED API，graph CSV 仅 fallback。
- Validate USPTO Open Data Portal patent table/API endpoint, then materialize patent/application/assignee tables as technology signal only.
- Build value/unit/period/product parser for `company_product_operating_metric_candidates_v0_1.jsonl` before any company product KPI promotion.
- Wire normalized evidence rows and public-source inventory into Evidence Fusion behind feature flags and source-boundary gates.

## Safety Notes

- `.env` 仍为 ignored local file；worklog、manifest、metadata 只记录环境变量名，不记录 key 值。
- Yahoo chart 保持 `unofficial_provisional`；不能作为 authoritative pricing、valuation 或 consensus。
- GDELT / Common Crawl / OpenAlex / Wikidata 只作为 lead/resolver/context，不允许直接写成事实结论。
