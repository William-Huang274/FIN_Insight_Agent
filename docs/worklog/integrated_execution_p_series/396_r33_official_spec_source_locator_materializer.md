# 396 R33 Official Spec Source Locator / Materializer

Date: 2026-06-25

## Scope

This checkpoint continues R32 ProductSpec / BusinessProfile depth work. The goal was not to relax the depth gate. The goal was to make the missing `technical_product_spec` and `business_asset_profile_spec` routes materially fetchable and parser-backed:

1. Locate issuer-domain official detail pages from already materialized official product pages.
2. Fetch those detail pages into raw / clean artifacts.
3. Parse only value/unit/product/citation rows into runtime context rows.
4. Keep candidate-only URLs, blocked pages, generic pages, loyalty/commerce noise, and date/count noise out of evidence.

## Implemented

- Added `scripts/data_expansion/build_official_spec_source_locator.py`.
  - Reads materialized `company_product_pages` raw HTML.
  - Extracts same-domain candidate links for `technical_product_spec` and `business_asset_profile_spec`.
  - Emits `official_spec_source_locator_candidates_v0_1.jsonl`.
  - Locator rows are not evidence and cannot enter ClaimCard / Memo.
- Added `scripts/data_expansion/materialize_official_spec_source_pages.py`.
  - Fetches locator candidates concurrently.
  - Writes raw and clean artifacts under `Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/official_spec_pages/`.
  - Handles HTML text and PDF text extraction through local `pypdf`.
  - Writes failed fetch/parse attempts into `official_spec_source_materialization_attempts_v0_1.jsonl`.
- Updated `build_official_product_spec_context_rows.py`.
  - Added `--additional-input`.
  - Added technical units for CUDA/tensor/RT cores, vCPU/CPU/GPU counts, threads, transistors, and parameters.
  - Added `billion/million/trillion` scale support for parameters/transistors.
- Updated `build_official_business_asset_profile_context_rows.py`.
  - Added `--additional-input`.
  - Expanded from V7-only MW/kW capacity to V7/V8 business footprint units: MW/GW/kW, sq ft, rooms, properties, stores/locations/branches, sites/facilities/plants/data centers, miles/km, acres.
  - Added noise guards for loyalty miles, year-like asset counts, zero asset counts, and unsupported bed counts.
  - Bed counts are explicitly deferred to a future V4 healthcare-facility adapter.
- Updated `src/sec_agent/product_family_source_routes.py`.
  - V8 physical-footprint families now get `business_asset_profile_spec` routes.

## Results

First locator/materialization run:

- Locator input: `971` official product pages and `3,412` route rows.
- Locator output: `470` candidates / `117` tickers.
  - `technical_product_spec=209`
  - `business_asset_profile_spec=261`
- Materializer selected `293` candidates.
  - `251` materialized
  - `36` unusable responses
  - `6` fetch failures
  - output detail artifacts: `245` rows / `104` tickers

Second locator/materialization run after V8 route expansion:

- Locator output: `347` candidates / `93` tickers.
- `--skip-existing` materializer selected `56` new candidates.
  - `16` newly materialized
  - official spec/profile detail artifact total: `260` rows / `110` tickers

Final parser-backed rows:

- `official_product_spec_context_rows_v0_1.jsonl`
  - `242` rows
  - `31` tickers
  - key metrics: memory, bandwidth, process node, power, range, camera/video, accelerator count, compute core count.
- `official_business_asset_profile_context_rows_v0_1.jsonl`
  - `56` rows
  - `27` tickers
  - key metrics: area, property/site count, store/location count, network/pipeline length, land area, generation/cooling/power capacity, room count.

Latest route/depth artifacts:

- `family_source_route_plan_v0_1.jsonl`
  - `route_plan_count=3,459`
  - `runtime_family_row_available=729`
  - `runtime_company_row_available=432`
  - `not_materialized=2,298`
- `second_third_layer_depth_parity_summary_v0_1.json`
  - `product_spec_depth=53/603`
  - `product_spec_parser_depth_gap=414`
  - `product_spec_source_or_parser_gap=136`
  - Product/Business-KPI remains `400/603`
  - CustomerDeployment remains `158/603`
  - CapitalMarketDetail remains `247/603`
  - MarketLiquidity remains `603/603`
  - full parity remains `3/603`

## Noise Repairs

During sample audit, the expanded business-profile parser initially admitted noisy rows. These were fixed before closing the checkpoint:

- Airline loyalty miles are rejected and no longer count as network/pipeline length.
- Year-like counts such as `2026 properties` are rejected for property/store/facility units.
- Zero store/location/property counts are rejected.
- `bed` units are rejected in V7/V8; healthcare bed/facility metrics require a future V4 adapter.
- MW/GW/kW unit classification now takes priority over incidental `site/property` words in the citation window.

## Boundary

R33 proves the official detail-page locator/fetch/parser path works. It does not prove broad product/SKU coverage. The remaining gaps are still real:

- `414` companies have official product taxonomy/catalog/surface rows but no parsed spec/profile slot.
- `136` companies still need better source locator/materialization routes for spec/profile.
- No candidate-only URL, blocked page, fetch attempt, generic product page, loyalty page, or noisy count row is allowed into runtime evidence.

## Verification

- `python -m pytest tests/test_official_product_spec_context_rows.py tests/test_official_business_asset_profile_context_rows.py tests/test_product_family_source_routes.py tests/test_official_spec_source_locator.py tests/test_official_spec_source_materializer.py -q` -> `22 passed`
- Rebuilt:
  - `official_spec_source_locator_candidates_v0_1.jsonl`
  - `official_spec_source_materialization_attempts_v0_1.jsonl`
  - `official_spec_source_materialization_summary_v0_1.json`
  - `official_product_spec_context_rows_v0_1.jsonl`
  - `official_business_asset_profile_context_rows_v0_1.jsonl`
  - `family_source_route_plan_v0_1.jsonl`
  - `second_third_layer_depth_parity_matrix_v0_1.jsonl`
  - `second_third_layer_depth_parity_gap_action_plan_v0_1.jsonl`

## Next

Continue second-layer depth work from the remaining `550` product-spec/profile gaps:

1. Build family-specific source locators rather than a generic official-page link scanner.
2. Add browser-rendered locator/fetch for JS-heavy product/spec pages.
3. Add PDF table/technical-document parser for semicap, hardware, auto, healthcare labels, and REIT/utility reports.
4. Split healthcare facility bed/procedure metrics into a V4-specific adapter.
5. Add software/cloud docs/API/instance-spec adapters for V3 rather than expecting generic product pages to expose numeric specs.
