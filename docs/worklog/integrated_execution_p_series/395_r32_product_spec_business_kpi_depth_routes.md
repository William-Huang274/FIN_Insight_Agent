# 395 R32 Product Spec / Business KPI Depth Routes

Date: 2026-06-25

## Scope

This checkpoint continues the second/third-layer depth parity work after R30/R31. It does not close the 603-company parity target. It fixes two data-layer problems that were blocking truthful coverage accounting:

1. Product pages were too weak to count as technical specs.
2. Business/industry operating metrics were available but not counted in the Product/Business-KPI depth matrix.

## Implemented

- Added `scripts/data_expansion/build_official_product_spec_context_rows.py`.
  - Extracts conservative official technical spec rows from materialized company product pages.
  - Emits `technical_product_spec` / `ProductSpecSlot` rows only when `spec_name/value/unit/product/citation` can be parsed.
  - Rejects commercial/site noise, trade-in/pricing text, PDF/file-size context, generic product-family pages, third-party infrastructure specs, support-hour text, and non-product percentages.
  - Output: `data/manifests/official_product_spec_context_rows_v0_1.jsonl`.
- Added `scripts/data_expansion/build_official_business_asset_profile_context_rows.py`.
  - Extracts bounded business/asset profile capacity rows for V7 asset-heavy companies.
  - Emits `business_asset_profile_spec` / `BusinessProfileSlot` rows.
  - This is not ProductSpecSlot and cannot prove revenue, backlog, order value, utilization, shipments, ASP, or market share.
  - Output: `data/manifests/official_business_asset_profile_context_rows_v0_1.jsonl`.
- Expanded Product/Business-KPI depth.
  - `industry_operating_metric_slot_rows_v0_1.jsonl` now enters the Product/Business-KPI depth audit.
  - Gate accepts only exact/runtime rows with value, unit, period, segment/product, and row-level claim boundary.
- Added `scripts/data_expansion/build_second_third_layer_depth_gap_action_plan.py`.
  - Builds per-company, per-dimension action rows from the latest depth parity matrix.
  - Each row carries lane, family scope, gap class, source-gap type, recommended routes, attempt policy, and claim boundary.
  - Output: `data/manifests/second_third_layer_depth_parity_gap_action_plan_v0_1.jsonl`.
- Expanded product-family source routes.
  - Non-fallback V1-V5 families now require `technical_product_spec` route.
  - V7 families now require `business_asset_profile_spec`; selected V7 equipment / power / battery / cooling families also require `technical_product_spec`.
  - Route registry no longer lets generic `company_product_pages` satisfy `business_asset_profile_spec`.

## Latest Metrics

After rebuilding ProductSpec rows, BusinessAssetProfile rows, depth parity matrix, route plan, and action plan:

- `product_kpi_depth=400/603`, up from `234/603`.
- `product_spec_depth=20/603`, up from `1/603`.
- `customer_deployment_depth=158/603`, unchanged.
- `capital_market_detail_depth=247/603`, unchanged.
- `market_liquidity_depth=603/603`, unchanged.
- `full_depth_target_met_company_count=3/603`.
- Remaining gap action rows: `1,587` across `600` tickers.

Gap action plan:

- Product/Business-KPI gaps: `203`.
- ProductSpec/Profile gaps: `583`.
- CustomerDeployment gaps: `445`.
- CapitalMarketDetail gaps: `356`.
- Source gap types:
  - `parser_or_join_gap=977`
  - `source_locator_or_materialization_gap=461`
  - `classified_public_boundary_or_deep_adapter_gap=149`

Route plan after source-route expansion:

- `route_plan_count=3,412`.
- `technical_product_spec`: `250` route rows; `21` runtime-ready, `229` not materialized.
- `business_asset_profile_spec`: `211` route rows; `3` runtime-ready, `208` not materialized.
- Overall route statuses: `runtime_family_row_available=685`, `runtime_company_row_available=433`, `not_materialized=2,294`.

## Boundary

R32b improves the data ledger and admits stronger exact/business rows where they already exist. It does not pretend public sources disclose product/SKU sales, ASP, market share, sell-through, backlog, or order value.

For product specs, ordinary product pages still do not count. A row must be parser-backed as `technical_product_spec` or bounded `business_asset_profile_spec`.

## Verification

- `python -m pytest tests/test_official_product_spec_context_rows.py tests/test_official_business_asset_profile_context_rows.py tests/test_second_third_layer_depth_parity_matrix.py tests/test_second_third_layer_depth_gap_action_plan.py tests/test_product_family_source_routes.py -q`
- `python -m py_compile scripts/data_expansion/build_official_product_spec_context_rows.py scripts/data_expansion/build_official_business_asset_profile_context_rows.py scripts/data_expansion/build_second_third_layer_depth_gap_action_plan.py src/sec_agent/layer_acceptance_gates.py src/sec_agent/product_family_source_routes.py`

## Next

1. Use `second_third_layer_depth_parity_gap_action_plan_v0_1.jsonl` to drive real source materialization, starting with `technical_product_spec` and `business_asset_profile_spec` not-materialized routes.
2. Build family-specific locator/fetch/parser batches for:
   - V1 semis/AI: datasheets, architecture pages, qualified systems, OEM configs.
   - V3 software/cloud: API docs, pricing/docs/status/release notes, marketplace listings.
   - V4 healthcare: labels, prescribing info, device product pages, ClinicalTrials/openFDA context.
   - V5 auto: model spec pages, NHTSA/recall/model APIs, battery/charging technical pages.
   - V7 energy/industrial: project/asset capacity pages, equipment datasheets, EIA/FERC/local regulatory asset context.
3. Continue R33/R34 after R32 source materialization is no longer dominated by parser/source-route gaps.
