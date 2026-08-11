# P34 AI/Semis Live Route Attempt Report v0.1

日期：2026-07-08

状态：`live_route_attempts_recorded_with_remaining_typed_gaps`

## 1. 结论

本报告把 P34 的重点 evidence slots 接到真实 source route attempts 或 attempt-backed typed gaps。
它不是 paid Memo Writer、full-chain 或模型对比；它只回答“哪些 source route 已尝试、哪些 row 可提权、哪些缺口有 attempt 依据”。

## 2. Metrics

- attempt_count：`21`
- attempted_slot_count：`20`
- accepted_runtime_row_count：`21`
- accepted_slot_count：`20`
- typed_gap_count：`2`
- attempt_backed_gap_slot_count：`2`
- unattempted_slot_count：`0`
- network_attempt_count：`15`
- network_ok_count：`15`
- perform_network：`True`

## 3. Accepted Runtime Rows

| Slot | Issuer | Metric | Authority |
| --- | --- | --- | --- |
| `amat_semiconductor_systems_mix` | `AMAT` | `equipment_segment_mix` | `May support company-disclosed product KPI facts from structured row/column cells; does not prove market share, channel inventory, or undisclosed product economics.` |
| `amzn_aws_demand_pool_context` | `AMZN` | `aws_revenue_operating_income` | `May support company-disclosed product KPI facts from structured row/column cells; does not prove market share, channel inventory, or undisclosed product economics.` |
| `nvda_gb200_nvl72_rack_architecture` | `NVDA` | `rack_scale_architecture` | `Official technical product specification. Supports bounded product capability/generation/comparison analysis only; no product revenue, unit sales, ASP, share, inventory, sell-through, backlog, customer order value, or demand proof.` |
| `tsmc_advanced_node_hpc_ai_readthrough` | `TSM` | `advanced_node_revenue_margin` | `Company-disclosed product/business revenue-mix percentage for the cited product or business line only; do not convert to absolute revenue, ASP, volume, market share, sell-through, backlog, or order value.` |
| `dell_ai_server_orders_shipments_backlog` | `DELL` | `orders_shipments_backlog` | `issuer_exact_operating_metric_with_margin_gap` |
| `dell_isg_revenue_margin_baseline` | `DELL` | `isg_revenue_operating_income_margin` | `issuer_exact_segment_metric_not_ai_server_margin` |
| `dell_nvidia_poweredge_ai_factory_product_path` | `DELL` | `official_oem_product_path` | `official_oem_product_path_not_order_value_or_margin` |
| `dell_xe9712_gb200_oem_system_config` | `DELL` | `oem_system_configuration` | `official_configuration_not_customer_purchase_or_margin` |
| `nvda_data_center_revenue_demand_confirmation` | `NVDA` | `data_center_revenue` | `issuer_exact_segment_metric_not_sku_revenue` |
| `amd_mi300x_memory_bandwidth_competition` | `AMD` | `accelerator_memory_bandwidth_spec` | `official_technical_fact_not_revenue_or_share` |
| `amd_mi300x_memory_bandwidth_competition` | `AMD` | `accelerator_memory_bandwidth_spec` | `official_technical_fact_not_revenue_or_share` |
| `google_tpu_v6e_trillium_architecture` | `GOOGL` | `custom_accelerator_architecture_spec` | `official_technical_fact_not_revenue_or_share` |
| `amd_mlperf_mi355x_performance_proxy` | `AMD` | `mlperf_inference_performance_proxy` | `performance_proxy_not_sales_or_share` |
| `google_a4x_gb200_cloud_deployment_surface` | `GOOGL` | `cloud_deployment_surface` | `official_deployment_signal_not_supplier_revenue_or_share` |
| `msft_cloud_ai_capex_supply_shortfall` | `MSFT` | `cloud_ai_capex_context` | `demand_pool_context_not_supplier_allocation` |
| `alphabet_capex_server_chain_context` | `GOOGL` | `technical_infrastructure_capex_context` | `demand_pool_context_not_supplier_allocation` |
| `meta_capex_component_pricing_risk` | `META` | `ai_infrastructure_capex_and_component_cost_risk` | `demand_pool_and_cost_risk_context_not_supplier_allocation` |
| `asml_lithography_installed_base_readthrough` | `ASML` | `lithography_cycle_disclosure` | `semicap_primary_disclosure_context_or_exact_if_table_bound` |
| `lrcx_memory_hbm_process_intensity` | `LRCX` | `memory_hbm_process_intensity_context` | `semicap_process_intensity_context_not_customer_order` |
| `market_price_in_valuation_positioning_gap` | `AI_SEMIS_BASKET` | `market_price_in_capital_feedback_context` | `market_context_not_fundamental_fact_or_realtime_flow` |
| `counter_thesis_pack_ai_semis` | `AI_SEMIS_BASKET` | `independent_counter_thesis_context` | `counterevidence_context_with_explicit_cannot_infer` |

## 4. Typed Gaps

| Slot | Gap | Reason |
| --- | --- | --- |
| `dell_ai_server_margin_bridge_quality_gap` | `source_absent_after_attempt` | Public issuer rows can support AI server revenue visibility and ISG baseline, but do not disclose AI server mix, GPU pass-through cost, or AI server gross margin. |
| `market_price_in_exact_positioning_gap` | `commercial_gap` | Public delayed/context rows can support price-in discussion, but exact crowding, real-time flow, complete options positioning, borrow cost and institutional flow need licensed feeds or deeper adapters. |

## 5. Boundary

- Accepted rows can support P34 no-paid audit, but cannot exceed each row's `authority_scope` / `cannot_infer` boundary.
- Typed gaps are useful only because they are attempt-backed; whether they block or allow a bounded scoped writer is decided by the P34 no-paid quality audit.
- Market context and counter-thesis context are not fundamental facts and must not be used as revenue/margin evidence.
