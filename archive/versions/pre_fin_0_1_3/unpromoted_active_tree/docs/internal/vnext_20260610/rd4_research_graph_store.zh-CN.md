# RD4 Research Graph Store v0.1

- Generated at: `2026-06-26T17:29:52+00:00`
- Status: `pass`
- Nodes: `26538`
- Edges: `100145`
- Evidence support rows: `113199`
- Dangling edges: `0`
- Unsupported edges: `0`

## Outputs

- `nodes`: `D:\FIN_Insight_Agent\data\manifests\research_graph_nodes_v0_1.jsonl`
- `edges`: `D:\FIN_Insight_Agent\data\manifests\research_graph_edges_v0_1.jsonl`
- `evidence_support`: `D:\FIN_Insight_Agent\data\manifests\research_graph_evidence_support_v0_1.jsonl`
- `sqlite`: `D:\FIN_Insight_Agent\data\workbench_private\research_data\research_graph_store_v0_1.sqlite`
- `summary`: `D:\FIN_Insight_Agent\data\manifests\research_graph_summary_v0_1.json`
- `report`: `D:\FIN_Insight_Agent\docs\internal\vnext_20260610\rd4_research_graph_store.zh-CN.md`

## Node Types

| Node type | Count |
| --- | ---: |
| `company` | `603` |
| `company_product_family` | `663` |
| `counterparty` | `5` |
| `external_counterparty` | `321` |
| `fact_or_signal_type` | `4410` |
| `product_context` | `13796` |
| `product_family` | `79` |
| `product_slot` | `6521` |
| `unknown_issuer` | `140` |

## Edge Authority

| Authority | Edges |
| --- | ---: |
| `bounded_thesis_driver_authority` | `69333` |
| `exact_company_fact_authority` | `30722` |
| `planning_or_gap_only` | `90` |

## Support Status

| Support | Rows |
| --- | ---: |
| `gold_mart_row` | `92017` |
| `modelled_relationship_without_direct_evidence_ref` | `65` |
| `source_evidence_ref_only` | `17585` |
| `structural_graph_topology_no_external_ref` | `3532` |

## Boundary

- RD4 不新增事实提权；图边 authority 继承 RD3 Gold Mart 或原 ProductRelationshipGraph 边界。
- `source_evidence_ref_only` 表示原图边已有 evidence_ref 但未映射到 Gold Mart row，仍保持原 claim boundary。
- Memo/ClaimCard 不能只因为图边存在就推断销量、ASP、份额、订单值、backlog 或实时资金流。
