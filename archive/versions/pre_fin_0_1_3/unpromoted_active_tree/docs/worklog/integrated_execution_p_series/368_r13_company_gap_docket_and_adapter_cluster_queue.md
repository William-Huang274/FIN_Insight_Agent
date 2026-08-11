# 368 R13 Company Gap Docket And Adapter Cluster Queue

日期：2026-06-19

## 问题

用户要求继续推进逐公司 gap 优化，目标不是“手工看 603 家网页”，而是把剩余 source-role / Product-KPI gap 全部结构化成可执行 docket，再按 cluster 批量修 adapter；任何 final gap 必须有 attempt ledger 支撑。

## 决策

1. 不直接放宽 evidence gate，也不把 L2/L3 proxy 填进 Product-KPI exact slot。
2. 先把 `exact_slot_gap_closeout_v0_1` 和 `product_kpi_deep_gap_diagnostic_v0_1` 合并为 company-level `CompanyGapDocket`。
3. 每条 docket 必须有 `cluster_id`、`adapter_family`、`source_ladder`、`pass_condition`、`final_gap_allowed_only_after`，否则 strict gate 失败。

## 完成工作

- 新增 `scripts/data_expansion/build_company_gap_docket.py`。
- 新增 `tests/test_company_gap_docket.py`。
- 生成：
  - `data/manifests/company_gap_docket_v0_1.jsonl`
  - `data/manifests/company_gap_adapter_cluster_queue_v0_1.jsonl`
  - `data/manifests/company_gap_docket_summary_v0_1.json`
  - `docs/internal/vnext_20260610/vertical_lanes/company_gap_docket.zh-CN.md`
- 更新 `docs/architecture/agent_graph_vnext/19_source_role_product_kpi_exact_slot_deep_repair.zh-CN.md`、`docs/worklog/README.md`、`docs/worklog/00_internal_master_checklist.md`。

## 结果

- `docket_count=591`
- `source_role_gap_docket_count=203`
- `product_kpi_gap_docket_count=388`
- `unique_gap_company_count=434`
- `cluster_count=15`
- `unclassified_docket_count=0`

Top adapter clusters:

| cluster | docket_count | priority |
| --- | ---: | --- |
| `product_kpi_source_specific_table_verifier` | 272 | high |
| `channel_offer_distributor_marketplace_adapter` | 53 | high |
| `developer_ecosystem_official_seed_locator` | 29 | high |
| `product_kpi_non_us_ir_local_exchange_parser` | 15 | high |
| `public_order_local_tender_and_recipient_adapter` | 12 | high |
| `regulated_product_context_regulatory_api_adapter` | 9 | high |
| `public_order_non_us_local_tender_adapter` | 7 | high |
| `supply_chain_official_relationship_resolver` | 4 | high |
| `regulated_product_animal_health_veterinary_adapter` | 2 | high |

## 验证

已运行：

```powershell
python -m pytest tests\test_company_gap_docket.py -q
python -m py_compile scripts\data_expansion\build_company_gap_docket.py
python scripts\data_expansion\build_company_gap_docket.py --strict
```

结果：

- `2 passed`
- `build_company_gap_docket.py --strict` 通过，`unclassified_docket_count=0`

## 后续

下一轮应开始执行 cluster batch，而不是继续写总表：

1. `product_kpi_source_specific_table_verifier`
2. `channel_offer_distributor_marketplace_adapter`
3. `developer_ecosystem_official_seed_locator`
4. `product_kpi_non_us_ir_local_exchange_parser`
5. `public_order_local_tender_and_recipient_adapter`
6. `regulated_product_context_regulatory_api_adapter`

每个 batch 的通过条件是：ready row 增加，或对应 company/family/source ladder 写出 attempt-backed final gap；不能出现 unattempted final gap。
