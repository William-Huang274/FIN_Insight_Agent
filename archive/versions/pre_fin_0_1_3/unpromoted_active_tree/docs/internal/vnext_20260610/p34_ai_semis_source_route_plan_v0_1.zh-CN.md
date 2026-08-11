# P34 AI/Semis Source Route Plan v0.1

日期：2026-07-08

## 1. 结论

本轮把 P34 的 20 个 AI/Semis evidence slots 转成 source route plan。它只是 route/parser 执行前的机器可读计划，不代表已经完成 live source、爬虫、parser 或 runtime row 提权。

当前状态：`source_route_plan_ready_adapter_fixtures_pending`。

## 2. Metrics

- `slot_count`: `20`
- `route_count`: `47`
- `primary_route_count`: `20`
- `fallback_route_count`: `27`
- `slot_with_primary_route_count`: `20`
- `slot_with_fallback_route_count`: `20`
- `route_gap_count`: `0`
- `adapter_family_count`: `15`

## 3. Adapter Family Counts

- `benchmark_result_adapter`: `1`
- `cloud_capex_filing_adapter`: `3`
- `credit_or_debt_context_adapter`: `1`
- `customer_deployment_news_adapter`: `2`
- `investor_deck_pdf_table_adapter`: `11`
- `market_snapshot_context_adapter`: `2`
- `oem_configuration_adapter`: `2`
- `official_product_docs_or_pdf_adapter`: `5`
- `official_product_spec_page_adapter`: `7`
- `options_or_short_interest_proxy_adapter`: `1`
- `ownership_filing_context_adapter`: `1`
- `regulatory_or_export_control_adapter`: `1`
- `risk_counterevidence_context_adapter`: `1`
- `sec_8k_earnings_release_table_adapter`: `6`
- `semicap_bookings_backlog_adapter`: `3`

## 4. Slots

| Slot | Status | Primary route | Fallback routes |
| --- | --- | --- | --- |
| `dell_ai_server_orders_shipments_backlog` | `route_plan_ready_parser_lineage_repair_required` | `p34_route::dell_ai_server_orders_shipments_backlog::01::sec_8k_earnings_release_table_adapter` | p34_route::dell_ai_server_orders_shipments_backlog::02::investor_deck_pdf_table_adapter |
| `dell_isg_revenue_margin_baseline` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::dell_isg_revenue_margin_baseline::01::sec_8k_earnings_release_table_adapter` | p34_route::dell_isg_revenue_margin_baseline::02::investor_deck_pdf_table_adapter |
| `dell_nvidia_poweredge_ai_factory_product_path` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::dell_nvidia_poweredge_ai_factory_product_path::01::official_product_spec_page_adapter` | p34_route::dell_nvidia_poweredge_ai_factory_product_path::02::customer_deployment_news_adapter, p34_route::dell_nvidia_poweredge_ai_factory_product_path::03::oem_configuration_adapter, p34_route::dell_nvidia_poweredge_ai_factory_product_path::04::official_product_docs_or_pdf_adapter |
| `dell_xe9712_gb200_oem_system_config` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::dell_xe9712_gb200_oem_system_config::01::official_product_spec_page_adapter` | p34_route::dell_xe9712_gb200_oem_system_config::02::oem_configuration_adapter, p34_route::dell_xe9712_gb200_oem_system_config::03::official_product_docs_or_pdf_adapter |
| `nvda_gb200_nvl72_rack_architecture` | `route_plan_ready_existing_live_row_requires_revalidation` | `p34_route::nvda_gb200_nvl72_rack_architecture::01::official_product_spec_page_adapter` | p34_route::nvda_gb200_nvl72_rack_architecture::02::official_product_docs_or_pdf_adapter |
| `nvda_data_center_revenue_demand_confirmation` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::nvda_data_center_revenue_demand_confirmation::01::sec_8k_earnings_release_table_adapter` | p34_route::nvda_data_center_revenue_demand_confirmation::02::investor_deck_pdf_table_adapter |
| `amd_mi300x_memory_bandwidth_competition` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::amd_mi300x_memory_bandwidth_competition::01::official_product_spec_page_adapter` | p34_route::amd_mi300x_memory_bandwidth_competition::02::official_product_docs_or_pdf_adapter |
| `amd_mlperf_mi355x_performance_proxy` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::amd_mlperf_mi355x_performance_proxy::01::benchmark_result_adapter` | p34_route::amd_mlperf_mi355x_performance_proxy::02::official_product_spec_page_adapter |
| `google_tpu_v6e_trillium_architecture` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::google_tpu_v6e_trillium_architecture::01::official_product_spec_page_adapter` | p34_route::google_tpu_v6e_trillium_architecture::02::official_product_docs_or_pdf_adapter |
| `google_a4x_gb200_cloud_deployment_surface` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::google_a4x_gb200_cloud_deployment_surface::01::customer_deployment_news_adapter` | p34_route::google_a4x_gb200_cloud_deployment_surface::02::official_product_spec_page_adapter |
| `msft_cloud_ai_capex_supply_shortfall` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::msft_cloud_ai_capex_supply_shortfall::01::cloud_capex_filing_adapter` | p34_route::msft_cloud_ai_capex_supply_shortfall::02::investor_deck_pdf_table_adapter |
| `amzn_aws_demand_pool_context` | `route_plan_ready_existing_live_row_requires_revalidation` | `p34_route::amzn_aws_demand_pool_context::01::sec_8k_earnings_release_table_adapter` | p34_route::amzn_aws_demand_pool_context::02::investor_deck_pdf_table_adapter |
| `alphabet_capex_server_chain_context` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::alphabet_capex_server_chain_context::01::cloud_capex_filing_adapter` | p34_route::alphabet_capex_server_chain_context::02::sec_8k_earnings_release_table_adapter, p34_route::alphabet_capex_server_chain_context::03::investor_deck_pdf_table_adapter |
| `meta_capex_component_pricing_risk` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::meta_capex_component_pricing_risk::01::cloud_capex_filing_adapter` | p34_route::meta_capex_component_pricing_risk::02::investor_deck_pdf_table_adapter |
| `tsmc_advanced_node_hpc_ai_readthrough` | `route_plan_ready_existing_live_row_requires_revalidation` | `p34_route::tsmc_advanced_node_hpc_ai_readthrough::01::investor_deck_pdf_table_adapter` | p34_route::tsmc_advanced_node_hpc_ai_readthrough::02::sec_8k_earnings_release_table_adapter |
| `asml_lithography_installed_base_readthrough` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::asml_lithography_installed_base_readthrough::01::semicap_bookings_backlog_adapter` | p34_route::asml_lithography_installed_base_readthrough::02::investor_deck_pdf_table_adapter |
| `amat_semiconductor_systems_mix` | `route_plan_ready_existing_live_row_requires_revalidation` | `p34_route::amat_semiconductor_systems_mix::01::semicap_bookings_backlog_adapter` | p34_route::amat_semiconductor_systems_mix::02::investor_deck_pdf_table_adapter |
| `lrcx_memory_hbm_process_intensity` | `route_plan_ready_adapter_fixture_required_before_promotion` | `p34_route::lrcx_memory_hbm_process_intensity::01::semicap_bookings_backlog_adapter` | p34_route::lrcx_memory_hbm_process_intensity::02::investor_deck_pdf_table_adapter |
| `market_price_in_valuation_positioning_gap` | `route_plan_ready_case_binding_required_before_lookup` | `p34_route::market_price_in_valuation_positioning_gap::01::market_snapshot_context_adapter` | p34_route::market_price_in_valuation_positioning_gap::02::ownership_filing_context_adapter, p34_route::market_price_in_valuation_positioning_gap::03::options_or_short_interest_proxy_adapter, p34_route::market_price_in_valuation_positioning_gap::04::credit_or_debt_context_adapter |
| `counter_thesis_pack_ai_semis` | `route_plan_ready_case_binding_required_before_lookup` | `p34_route::counter_thesis_pack_ai_semis::01::risk_counterevidence_context_adapter` | p34_route::counter_thesis_pack_ai_semis::02::market_snapshot_context_adapter, p34_route::counter_thesis_pack_ai_semis::03::regulatory_or_export_control_adapter |

## 5. 当前边界

- 没有运行 paid LLM。
- 没有运行 full-chain。
- 没有运行新爬虫或 parser。
- `route_plan_ready` 不等于 `live_runtime_ready`。
- weak candidate 仍不能进入正式 evidence bundle。

## 6. 下一步

Implement first adapter-family fixtures: sec_8k_earnings_release_table_adapter, official_product_spec_page_adapter, and semicap_bookings_backlog_adapter.
