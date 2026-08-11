# Product Family Source Route Plan

- registry_schema: `finsight_product_family_lane_registry_v0_1`
- family_count: `81`
- assignment_count: `663`
- route_plan_count: `4431`
- fetch_audit_status: `gap`
- runtime_family_ready_route_count: `1326`
- materialized_fetch_available_route_count: `0`
- seed_available_not_materialized_route_count: `0`
- not_materialized_route_count: `2472`

## Route Status

| status | count |
| --- | ---: |
| not_materialized | 2472 |
| runtime_company_row_available | 633 |
| runtime_family_row_available | 1326 |

## Lane Status

| lane | routes | runtime family | materialized only | seed only | missing |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 437 | 159 | 0 | 0 | 207 |
| V2 | 40 | 15 | 0 | 0 | 7 |
| V3 | 687 | 205 | 0 | 0 | 361 |
| V4 | 501 | 115 | 0 | 0 | 278 |
| V5 | 115 | 48 | 0 | 0 | 45 |
| V6 | 451 | 144 | 0 | 0 | 246 |
| V7 | 1627 | 445 | 0 | 0 | 1000 |
| V8 | 573 | 195 | 0 | 0 | 328 |

## Top Missing Routes

- `000660.KS` `memory` `macro_official_context`: `not_materialized`; next=discover_allowed_source_for_macro_official_context_then_fetch_parse_resolve
- `000660.KS` `memory` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `000660.KS` `memory` `technology_research_proxy`: `not_materialized`; next=discover_allowed_source_for_technology_research_proxy_then_fetch_parse_resolve
- `000660.KS` `memory` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `005930.KS` `foundry` `macro_official_context`: `not_materialized`; next=discover_allowed_source_for_macro_official_context_then_fetch_parse_resolve
- `005930.KS` `foundry` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `005930.KS` `foundry` `technology_research_proxy`: `not_materialized`; next=discover_allowed_source_for_technology_research_proxy_then_fetch_parse_resolve
- `005930.KS` `foundry` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `005930.KS` `memory` `macro_official_context`: `not_materialized`; next=discover_allowed_source_for_macro_official_context_then_fetch_parse_resolve
- `005930.KS` `memory` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `005930.KS` `memory` `technology_research_proxy`: `not_materialized`; next=discover_allowed_source_for_technology_research_proxy_then_fetch_parse_resolve
- `005930.KS` `memory` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `1211.HK` `battery_charging_autonomy` `business_service_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_service_profile_spec_then_fetch_parse_resolve
- `1211.HK` `battery_charging_autonomy` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `1211.HK` `battery_charging_autonomy` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `1211.HK` `ev_vehicle_platform` `business_service_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_service_profile_spec_then_fetch_parse_resolve
- `1211.HK` `ev_vehicle_platform` `channel_offer_proxy`: `not_materialized`; next=discover_allowed_source_for_channel_offer_proxy_then_fetch_parse_resolve
- `1211.HK` `ev_vehicle_platform` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `1211.HK` `ev_vehicle_platform` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `2308.TW` `power_cooling` `hiring_capacity_proxy`: `not_materialized`; next=discover_allowed_source_for_hiring_capacity_proxy_then_fetch_parse_resolve
- `2308.TW` `power_cooling` `macro_official_context`: `not_materialized`; next=discover_allowed_source_for_macro_official_context_then_fetch_parse_resolve
- `2308.TW` `power_cooling` `primary_company_disclosure`: `not_materialized`; next=discover_allowed_source_for_primary_company_disclosure_then_fetch_parse_resolve
- `2308.TW` `power_cooling` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `2308.TW` `power_cooling` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `2308.TW` `power_cooling` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `2308.TW` `power_grid_cooling` `business_asset_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_asset_profile_spec_then_fetch_parse_resolve
- `2308.TW` `power_grid_cooling` `business_service_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_service_profile_spec_then_fetch_parse_resolve
- `2308.TW` `power_grid_cooling` `energy_utility_context`: `not_materialized`; next=discover_allowed_source_for_energy_utility_context_then_fetch_parse_resolve
- `2308.TW` `power_grid_cooling` `hiring_capacity_proxy`: `not_materialized`; next=discover_allowed_source_for_hiring_capacity_proxy_then_fetch_parse_resolve
- `2308.TW` `power_grid_cooling` `primary_company_disclosure`: `not_materialized`; next=discover_allowed_source_for_primary_company_disclosure_then_fetch_parse_resolve
- `2308.TW` `power_grid_cooling` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `2308.TW` `power_grid_cooling` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `2317.TW` `electronics_manufacturing_services` `primary_company_disclosure`: `not_materialized`; next=discover_allowed_source_for_primary_company_disclosure_then_fetch_parse_resolve
- `2317.TW` `electronics_manufacturing_services` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `2317.TW` `electronics_manufacturing_services` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `2317.TW` `electronics_manufacturing_services` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `2382.TW` `electronics_manufacturing_services` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `2382.TW` `electronics_manufacturing_services` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `2382.TW` `electronics_manufacturing_services` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `300750.SZ` `battery_energy_storage_components` `business_asset_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_asset_profile_spec_then_fetch_parse_resolve
- `300750.SZ` `battery_energy_storage_components` `business_service_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_service_profile_spec_then_fetch_parse_resolve
- `300750.SZ` `battery_energy_storage_components` `energy_utility_context`: `not_materialized`; next=discover_allowed_source_for_energy_utility_context_then_fetch_parse_resolve
- `300750.SZ` `battery_energy_storage_components` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `300750.SZ` `battery_energy_storage_components` `technology_research_proxy`: `not_materialized`; next=discover_allowed_source_for_technology_research_proxy_then_fetch_parse_resolve
- `300750.SZ` `battery_energy_storage_components` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `3231.TW` `electronics_manufacturing_services` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `3231.TW` `electronics_manufacturing_services` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `3231.TW` `electronics_manufacturing_services` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `373220.KS` `battery_energy_storage_components` `business_asset_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_asset_profile_spec_then_fetch_parse_resolve
- `373220.KS` `battery_energy_storage_components` `business_service_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_service_profile_spec_then_fetch_parse_resolve
- `373220.KS` `battery_energy_storage_components` `energy_utility_context`: `not_materialized`; next=discover_allowed_source_for_energy_utility_context_then_fetch_parse_resolve
- `373220.KS` `battery_energy_storage_components` `primary_company_disclosure`: `not_materialized`; next=discover_allowed_source_for_primary_company_disclosure_then_fetch_parse_resolve
- `373220.KS` `battery_energy_storage_components` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `373220.KS` `battery_energy_storage_components` `technology_research_proxy`: `not_materialized`; next=discover_allowed_source_for_technology_research_proxy_then_fetch_parse_resolve
- `373220.KS` `battery_energy_storage_components` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `6146.T` `semicap_equipment` `primary_company_disclosure`: `not_materialized`; next=discover_allowed_source_for_primary_company_disclosure_then_fetch_parse_resolve
- `6146.T` `semicap_equipment` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `6146.T` `semicap_equipment` `supply_chain_official_relationship`: `not_materialized`; next=discover_allowed_source_for_supply_chain_official_relationship_then_fetch_parse_resolve
- `6146.T` `semicap_equipment` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `6146.T` `semicap_equipment` `technology_research_proxy`: `not_materialized`; next=discover_allowed_source_for_technology_research_proxy_then_fetch_parse_resolve
- `6146.T` `semicap_equipment` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `6723.T` `analog_embedded_semiconductors` `primary_company_disclosure`: `not_materialized`; next=discover_allowed_source_for_primary_company_disclosure_then_fetch_parse_resolve
- `6723.T` `analog_embedded_semiconductors` `technology_research_proxy`: `not_materialized`; next=discover_allowed_source_for_technology_research_proxy_then_fetch_parse_resolve
- `6723.T` `analog_embedded_semiconductors` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `6752.T` `industrial_equipment` `business_asset_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_asset_profile_spec_then_fetch_parse_resolve
- `6752.T` `industrial_equipment` `business_service_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_service_profile_spec_then_fetch_parse_resolve
- `6752.T` `industrial_equipment` `channel_offer_proxy`: `not_materialized`; next=discover_allowed_source_for_channel_offer_proxy_then_fetch_parse_resolve
- `6752.T` `industrial_equipment` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `6857.T` `semicap_equipment` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `6857.T` `semicap_equipment` `supply_chain_official_relationship`: `not_materialized`; next=discover_allowed_source_for_supply_chain_official_relationship_then_fetch_parse_resolve
- `6857.T` `semicap_equipment` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `6857.T` `semicap_equipment` `technology_research_proxy`: `not_materialized`; next=discover_allowed_source_for_technology_research_proxy_then_fetch_parse_resolve
- `6857.T` `semicap_equipment` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `8035.T` `semicap_equipment` `primary_company_disclosure`: `not_materialized`; next=discover_allowed_source_for_primary_company_disclosure_then_fetch_parse_resolve
- `8035.T` `semicap_equipment` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `8035.T` `semicap_equipment` `technology_research_proxy`: `not_materialized`; next=discover_allowed_source_for_technology_research_proxy_then_fetch_parse_resolve
- `8035.T` `semicap_equipment` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `A` `life_science_tools_diagnostics` `regulated_product_context`: `not_materialized`; next=discover_allowed_source_for_regulated_product_context_then_fetch_parse_resolve
- `A` `life_science_tools_diagnostics` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `A` `life_science_tools_diagnostics` `technology_research_proxy`: `not_materialized`; next=discover_allowed_source_for_technology_research_proxy_then_fetch_parse_resolve
- `A` `life_science_tools_diagnostics` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `A` `medtech_devices` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `A` `medtech_devices` `regulated_product_context`: `not_materialized`; next=discover_allowed_source_for_regulated_product_context_then_fetch_parse_resolve
- `A` `medtech_devices` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `A` `medtech_devices` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `AAPL` `pcs_peripherals` `platform_review_proxy`: `not_materialized`; next=discover_allowed_source_for_platform_review_proxy_then_fetch_parse_resolve
- `AAPL` `wearables_devices` `platform_review_proxy`: `not_materialized`; next=discover_allowed_source_for_platform_review_proxy_then_fetch_parse_resolve
- `ABBV` `oncology_immunology` `regulated_product_context`: `not_materialized`; next=discover_allowed_source_for_regulated_product_context_then_fetch_parse_resolve
- `ABBV` `oncology_immunology` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `ABBV` `oncology_immunology` `technology_research_proxy`: `not_materialized`; next=discover_allowed_source_for_technology_research_proxy_then_fetch_parse_resolve
- `ABNB` `travel_marketplace` `app_rank_store_proxy`: `not_materialized`; next=discover_allowed_source_for_app_rank_store_proxy_then_fetch_parse_resolve
- `ABNB` `travel_marketplace` `business_asset_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_asset_profile_spec_then_fetch_parse_resolve
- `ABNB` `travel_marketplace` `business_service_profile_spec`: `not_materialized`; next=discover_allowed_source_for_business_service_profile_spec_then_fetch_parse_resolve
- `ABNB` `travel_marketplace` `primary_company_disclosure`: `not_materialized`; next=discover_allowed_source_for_primary_company_disclosure_then_fetch_parse_resolve
- `ABT` `medtech_devices` `primary_company_disclosure`: `not_materialized`; next=discover_allowed_source_for_primary_company_disclosure_then_fetch_parse_resolve
- `ABT` `medtech_devices` `public_order_proxy`: `not_materialized`; next=discover_allowed_source_for_public_order_proxy_then_fetch_parse_resolve
- `ABT` `medtech_devices` `regulated_product_context`: `not_materialized`; next=discover_allowed_source_for_regulated_product_context_then_fetch_parse_resolve
- `ABT` `medtech_devices` `technical_product_spec`: `not_materialized`; next=discover_allowed_source_for_technical_product_spec_then_fetch_parse_resolve
- `ABT` `medtech_devices` `trusted_external_context`: `not_materialized`; next=discover_allowed_source_for_trusted_external_context_then_fetch_parse_resolve
- `ACGL` `v6_general_financials` `financial_regulatory_context`: `not_materialized`; next=discover_allowed_source_for_financial_regulatory_context_then_fetch_parse_resolve

## Boundary

Fetch audit checks whether family-scoped source routes already have runtime/parser rows or materialized source pages; it does not promote L2/L3 proxies to company exact facts.
