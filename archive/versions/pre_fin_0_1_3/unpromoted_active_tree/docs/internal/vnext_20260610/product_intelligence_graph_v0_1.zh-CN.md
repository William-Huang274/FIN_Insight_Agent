# ProductIntelligenceGraph v0.1

- Generated at: `2026-06-26T18:50:12Z`
- Status: `pass`
- Companies: `603`
- Nodes / edges: `36046` / `71034`
- Company packs: `603`
- Gap rows: `1140`
- Evidence-bundle eligible edges: `67343`

## Outputs

- `nodes`: `D:\FIN_Insight_Agent\data\manifests\product_intelligence_graph_nodes_v0_1.jsonl`
- `edges`: `D:\FIN_Insight_Agent\data\manifests\product_intelligence_graph_edges_v0_1.jsonl`
- `company_packs`: `D:\FIN_Insight_Agent\data\manifests\product_intelligence_company_pack_v0_1.jsonl`
- `gap_ledger`: `D:\FIN_Insight_Agent\data\manifests\product_intelligence_gap_ledger_v0_1.jsonl`
- `sqlite`: `D:\FIN_Insight_Agent\data\workbench_private\research_data\product_intelligence_graph_v0_1.sqlite`
- `summary`: `D:\FIN_Insight_Agent\data\manifests\product_intelligence_graph_summary_v0_1.json`
- `report`: `D:\FIN_Insight_Agent\docs\internal\vnext_20260610\product_intelligence_graph_v0_1.zh-CN.md`

## Authority Types

| Authority type | Edges |
| --- | ---: |
| `product_profile_authority` | 27740 |
| `product_taxonomy_context` | 20889 |
| `exact_product_kpi_authority` | 14910 |
| `competitive_context_candidate` | 3420 |
| `industry_operating_metric_authority` | 1923 |
| `deployment_signal_authority` | 1201 |
| `technical_fact_authority` | 484 |
| `supply_chain_signal` | 221 |
| `template_context_edge` | 127 |
| `channel_presence_signal` | 99 |
| `regulated_product_context_signal` | 20 |

## Company Pack Status

| Status | Companies |
| --- | ---: |
| `pass_with_gaps` | 585 |
| `pass` | 18 |

## Gaps

| Gap reason | Rows |
| --- | ---: |
| `technical_spec_exact_slot_absent` | 572 |
| `deployment_channel_supply_chain_signal_absent` | 404 |
| `product_kpi_or_operating_metric_absent` | 164 |

## Boundary

- Product-KPI exact remains strict and separate from product profile/spec/deployment signals.
- Technical specs can support capability, generation, architecture and comparison claims, not sales, ASP, share, backlog or shipment claims.
- Customer deployment, public order, channel and supply-chain edges support bounded thesis drivers only unless exact commercial fields are separately disclosed.
- Same-family competitive edges are comparable candidates; they do not prove share shift, win/loss, pricing pressure or substitution without stronger evidence.
