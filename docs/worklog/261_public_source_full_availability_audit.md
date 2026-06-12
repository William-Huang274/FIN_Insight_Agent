# 261 公开数据源 full availability audit

## Prompt

用户指出上一轮只做了 smoke，还没有确认 full 数据的可用性、可得性；在接入 source inventory / Evidence Fusion Selector 之前，应先把数据源可用性审计做完整。

## Decision

本轮不把 `public_source_normalized_smoke_v0_1` 直接接进 agent runtime。先新增 full availability audit，把每个 source plan row 分成：

- 已做 bounded live availability audit 的源；
- 只有 live probe、但还没有 normalized collector/parser 的源；
- source-plan-only、credential-blocked、commercial-deferred 的源。

审计输出继续只写小型 manifest，不写 raw payload、不写 private bulk data、不写密钥。所有 URL、错误和 manifest 只允许保留脱敏后的 endpoint/参数。

## Work Completed

- 新增 `scripts/data_expansion/audit_public_source_full_availability.py`。
- 新增 `tests/test_public_source_full_availability_audit.py`。
- 生成机器可读审计产物：
  - `data/manifests/public_source_full_availability_audit_v0_1.jsonl`
  - `data/manifests/public_source_full_availability_audit_summary_v0_1.json`
- 审计维度覆盖：
  - endpoint reachability / HTTP status；
  - bounded history 或 prior-window probe；
  - pagination / offset / second-page / skip 能力；
  - normalized field completeness；
  - target universe mapping requirement；
  - entity/product/security identifier mapping requirement；
  - claim boundary 和 agent promotion blocker。

## Result

本轮覆盖 `32` 个 source plan rows：

- live audited sources：`15`
  - normalized profile sources：`13`
  - probe-only sources：`2`
- live error sources：`0`
- status：`pass_with_blockers`
- agent promotion：`false`

当前可以作为候选、但仍必须经过 source inventory feature flag 和 source-boundary gate 的源：

- `fred_api`
- `bls_public_api`
- `bea_data_api`
- `sec_edgar_apis`
- `openfigi_api`

当前仍是 partial / not-ready：

- `census_data_api`：需要 dataset/table/geography contract。
- `eia_open_data`：需要 route/series allowlist 和 company/asset mapping gate。
- `fdic_bankfind_api`、`gleif_api`：需要 entity-to-issuer mapping。
- `clinicaltrials_api`：需要 sponsor/product/condition resolver。
- `openfda_api`：需要 endpoint allowlist 和 product/application/sponsor resolver；当前 `drug/drugsfda` sample 的 `status` 字段为空，不能当作稳定产品状态合同。
- `nhtsa_vpic_api`：需要 manufacturer/make/model/year 到 issuer 的 mapping。
- `kr_dart_openapi`：当前只验证 company reference，尚未验证 filing list/date-window/package parser。
- `fred_graph_csv`、`openalex_api`：只有 probe path，尚未进入 public normalized collector。
- `jp_edinet_api`：仍缺 `EDINET_API_KEY`。
- `commercial_market_data_and_consensus`：继续 `commercial_deferred`。
- 其余 portal/source-plan rows 继续保持 endpoint/profile validation pending。

## Validation

- `python -m py_compile scripts/data_expansion/audit_public_source_full_availability.py` -> pass
- `python -m pytest tests/test_public_source_full_availability_audit.py` -> `4 passed`
- `python scripts/data_expansion/audit_public_source_full_availability.py --allow-partial --timeout-s 30` -> pass with blockers, `15` live audited, live errors `0`

## Follow-up

- 不要先接 runtime。先把 `census_data_api`、`eia_open_data`、`clinicaltrials_api`、`openfda_api`、`nhtsa_vpic_api`、`fdic_bankfind_api`、`gleif_api` 的 mapping/endpoint gates 定义清楚。
- 对 `kr_dart_openapi` 增加 filing list/date-window/package parser audit；company reference 不能代表 DART filings 可用。
- 对 `openalex_api` 和 `fred_graph_csv` 决定是否纳入 normalized collector，或明确保留为 existing industry/probe-only source。
- 获得 `EDINET_API_KEY` 后再做 JP EDINET 官方 API audit。
- 只有通过上述 gate 的源才允许接入 source inventory / Evidence Fusion Selector。
