# RD3 Gold Fact / Signal Mart

- Generated at: `2026-06-26T17:20:29+00:00`
- Status: `pass`
- Rows: `74894`
- Companies: `603`
- Source rowsets: `17`
- Missing source rowsets: `0`
- SQLite rows: `74894`

## Outputs

- `gold_fact_signal_mart_rows`: `D:\FIN_Insight_Agent\data\manifests\gold_fact_signal_mart_rows_v0_1.jsonl`
- `gold_fact_signal_mart_source_rowsets`: `D:\FIN_Insight_Agent\data\manifests\gold_fact_signal_mart_source_rowsets_v0_1.jsonl`
- `sqlite`: `D:\FIN_Insight_Agent\data\workbench_private\research_data\gold_fact_signal_mart_v0_1.sqlite`
- `summary`: `D:\FIN_Insight_Agent\data\manifests\gold_fact_signal_mart_summary_v0_1.json`
- `report`: `D:\FIN_Insight_Agent\docs\internal\vnext_20260610\rd3_gold_fact_signal_mart.zh-CN.md`

## Authority

| Authority mode | Rows |
| --- | ---: |
| `bounded_thesis_driver_authority` | `44147` |
| `exact_company_fact_authority` | `30722` |
| `planning_or_gap_only` | `25` |

## Fact Domains

| Domain | Rows |
| --- | ---: |
| `capital_funding_ownership_fact` | `25055` |
| `customer_deployment_or_order_signal` | `370` |
| `financial_statement_fact` | `15849` |
| `industry_operating_metric_fact` | `1923` |
| `macro_industry_driver_signal` | `92` |
| `market_liquidity_signal` | `603` |
| `product_kpi_fact` | `7455` |
| `product_profile_or_spec_fact` | `16292` |
| `regulated_or_official_api_signal` | `74` |
| `source_authority` | `7181` |

## Support Surfaces

| Surface | Rows |
| --- | ---: |
| `capital_funding_ownership_market_liquidity` | `29123` |
| `channel_offer_availability_proxy` | `66` |
| `developer_ecosystem_proxy` | `64` |
| `fundamental_company_disclosure` | `16686` |
| `hiring_capacity_proxy` | `66` |
| `industry_competition_market_context` | `453` |
| `macro_industry_driver` | `758` |
| `official_customer_deployment_signal` | `371` |
| `official_customer_order_deployment_event` | `26` |
| `product_and_technology` | `10558` |
| `product_spec_and_capability` | `16295` |
| `public_order_supply_chain_proxy` | `159` |
| `regulated_product_context` | `146` |
| `regulated_product_identity` | `20` |
| `supply_chain_relationship` | `25` |
| `technology_research_ip` | `78` |

## Boundary

- RD3 只统一 accepted fact / bounded signal / source-authority row contract，不改变原始 authority。
- `planning_or_gap_only` 行只允许进入 planning/gap ledger，不允许进入 ClaimCard evidence bundle。
- Product spec、customer deployment、market liquidity、macro/context rows 可以支持 thesis driver，但不能冒充产品销量、ASP、份额、sell-through、backlog 或收入 exact。
