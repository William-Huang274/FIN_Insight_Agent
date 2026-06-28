# R43 ProductIntelligenceGraph v0.1

## Problem

RD0-RD7 已经把 raw provenance、parser ledger、Gold Mart、Graph Store、RAG index 和 runtime consumption contract 做成数据底座。但产品研究仍缺一个更直接的对象层：Research Lead / Product Specialist 需要看到的是公司产品、规格、产品 KPI、客户部署、渠道、供应链和竞争关系的统一 pack，而不是散装 `company_product_slots`、Gold Mart rows 和 product relationship edges。

用户明确要求：产品规格、架构、客户部署、供应链、竞品关系都应进入投研判断，但不能因为它们存在就冒充产品收入、销量、ASP、份额、sell-through、inventory 或 backlog。

## Decision

先实现 `ProductIntelligenceGraph v0.1`，不做新爬取、不改 Product-KPI exact gate，只归一化已有可信数据：

- `company_product_slots_v0_1`
- `product_relationship_graph_nodes/edges_v0_1`
- RD3 `gold_fact_signal_mart_rows_v0_1` 中 product/profile/spec/KPI/customer/regulated rows

输出四类对象：

- ProductIntelligence nodes
- ProductIntelligence edges
- per-company ProductEvidencePack
- ProductIntelligence gap ledger

Authority type 必须分层：

- `exact_product_kpi_authority`
- `industry_operating_metric_authority`
- `technical_fact_authority`
- `product_profile_authority`
- `deployment_signal_authority`
- `channel_presence_signal`
- `supply_chain_signal`
- `competitive_context_candidate`
- `template_context_edge`
- `regulated_product_context_signal`

## Work Completed

- 新增 `src/sec_agent/product_intelligence_graph.py`。
- 新增 `scripts/data_expansion/build_product_intelligence_graph.py`。
- 新增 `tests/test_product_intelligence_graph.py`，覆盖 authority 分层、template edge 防提权、technical spec forbidden claims、company pack 和 SQLite parity。
- 物化：
  - `data/manifests/product_intelligence_graph_nodes_v0_1.jsonl`
  - `data/manifests/product_intelligence_graph_edges_v0_1.jsonl`
  - `data/manifests/product_intelligence_company_pack_v0_1.jsonl`
  - `data/manifests/product_intelligence_gap_ledger_v0_1.jsonl`
  - `data/manifests/product_intelligence_graph_summary_v0_1.json`
  - `data/workbench_private/research_data/product_intelligence_graph_v0_1.sqlite`
  - `docs/internal/vnext_20260610/product_intelligence_graph_v0_1.zh-CN.md`
- 更新 24 文档和 master checklist。

## Result And Evidence

真实构建结果：

| Metric | Value |
| --- | ---: |
| status | `pass` |
| company packs | `603` |
| nodes | `36,046` |
| edges | `71,034` |
| evidence-bundle eligible edges | `67,343` |
| gap rows | `1,140` |
| SQLite nodes / edges / packs / gaps | `36,046 / 71,034 / 603 / 1,140` |
| dangling edges | `0` |
| invalid evidence edges | `0` |

Authority type counts:

| Authority | Edges |
| --- | ---: |
| `product_profile_authority` | `27,740` |
| `product_taxonomy_context` | `20,889` |
| `exact_product_kpi_authority` | `14,910` |
| `competitive_context_candidate` | `3,420` |
| `industry_operating_metric_authority` | `1,923` |
| `deployment_signal_authority` | `1,201` |
| `technical_fact_authority` | `484` |
| `supply_chain_signal` | `221` |
| `template_context_edge` | `127` |
| `channel_presence_signal` | `99` |
| `regulated_product_context_signal` | `20` |

Gap ledger:

- `technical_spec_exact_slot_absent=572`
- `deployment_channel_supply_chain_signal_absent=404`
- `product_kpi_or_operating_metric_absent=164`

这些 gap 是 Research Lead 的 targeted repair / boundary classification 输入，不是 Memo Writer 的兜底话术。

Verification:

- `python -m py_compile src/sec_agent/product_intelligence_graph.py scripts/data_expansion/build_product_intelligence_graph.py`
- `python -m pytest tests/test_product_intelligence_graph.py -q` -> `3 passed`
- `python scripts/data_expansion/build_product_intelligence_graph.py` -> `status=pass`

## Boundary And Follow-Up

- Product-KPI exact 仍保持严格；PIG 不把产品页、规格、部署、渠道、供应链信号升级成收入、销量、ASP、份额或 backlog。
- `template_context_edge` 不能进入 evidence bundle；same-family `COMPETES_WITH` 只是 comparable candidate，不证明 win/loss 或份额迁移。
- 下一步 PIG-2 应把 `product_intelligence_company_pack_v0_1` 接入 Research Lead / Product Specialist data view，并让 MemoLogicPlan 消费 Lead 组织后的产品逻辑，而不是让 Memo Writer 直接拼 raw slots。
