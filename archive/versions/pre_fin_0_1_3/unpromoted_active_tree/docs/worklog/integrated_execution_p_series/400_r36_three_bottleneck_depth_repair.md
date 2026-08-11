# 400 R36 Three Bottleneck Depth Repair

## Prompt

用户要求继续解决上一轮二三层 depth parity 中的三个主要瓶颈：Product-KPI exact 深度、CapitalMarketDetail 深度、ProductRelationshipGraph 关系图谱系统化。要求不能用弱 proxy 或 closeout row 糊住缺口，公开源能补的要补，不能补的要保留边界。

## Decision

本轮只做三类可审计修复：

- Product-KPI / operating metric verifier：只提权能被表内 column-group 求和验证的 aggregate total，不把 percentage/change、region-only、sentence relation 不足或 unresolved conflict 提权。
- Capital-market detail：扩大 SEC submissions metadata 覆盖，解决本地 cache 和 ticker mapping 漏洞；metadata 只作为 filing-event context，不当作 offering / ownership / insider transaction exact fact。
- ProductRelationshipGraph：把已经 parser-backed 的 official customer/deployment、supply-chain、public order/tender、channel/distribution rows 接入图谱边；这些边是关系/检索/推理上下文，不是销量、份额、ASP、订单金额或 backlog 事实。

## Work Completed

### Product-KPI / Operating Metric

- 更新 `scripts/data_expansion/build_industry_operating_metric_slot_rows.py`：
  - 新增 column-group conflict resolver。
  - 当一个冲突值等于兄弟 column-group 值之和时，选择该 aggregate row。
  - 兄弟 row 标记为 `conflict_resolved_non_aggregate_sibling`，未能证明 aggregate 的冲突继续拒绝。
- 更新 `tests/test_industry_operating_metric_slot_rows.py`：
  - 增加 aggregate total conflict resolution fixture。
- 重建：
  - `data/manifests/industry_operating_metric_slot_rows_v0_1.jsonl`
  - `data/manifests/industry_operating_metric_slot_rejections_v0_1.jsonl`
  - `data/manifests/industry_operating_metric_slot_summary_v0_1.json`
  - Product-KPI closeout / diagnostic / depth parity artifacts。

### CapitalMarketDetail

- 更新 `scripts/data_expansion/build_sec_capital_market_event_context_rows.py`：
  - 新增 `--fetch-missing-submissions` SEC submissions cache fetch。
  - 支持 company universe / ticker->CIK mapping / local cache / fetch ledger / concurrent fetch。
  - 支持 target ticker filtering，修复 multi-ticker issuer 只吐第一个 ticker 的问题。
- 更新 `tests/test_sec_capital_market_event_context_rows.py`：
  - 增加 materialize missing submissions test。
  - 增加 multi-ticker issuer projection test。
- 重建：
  - `data/manifests/sec_capital_market_event_context_rows_v0_1.jsonl`
  - `data/manifests/sec_capital_market_event_context_summary_v0_1.json`
  - `data/manifests/sec_capital_market_event_submission_fetch_ledger_v0_1.json`
  - depth parity / gap action plan / real-source readiness artifacts。

### ProductRelationshipGraph

- 更新 `src/sec_agent/product_slot_relationship_graph.py`：
  - 新增 `relationship_context_rows` 输入。
  - 新增 parser-backed relationship edge projection。
  - 新边类型：`OFFICIAL_CUSTOMER_DEPLOYMENT_EVENT`、`OFFICIAL_SUPPLY_CHAIN_RELATIONSHIP`、`PUBLIC_ORDER_OR_TENDER_CONTEXT`、`CHANNEL_OR_DISTRIBUTION_CONTEXT`。
- 更新 `scripts/data_expansion/build_product_slot_relationship_graph.py`：
  - 接入 official customer deployment、targeted supply chain、public contract award、local tender、family channel distributor 等 context row files。
- 更新 `tests/test_product_slot_relationship_graph.py`：
  - 增加 parser-backed relationship edge fixture。
- 重建：
  - `data/manifests/product_relationship_graph_nodes_v0_1.jsonl`
  - `data/manifests/product_relationship_graph_edges_v0_1.jsonl`
  - `data/manifests/product_relationship_graph_summary_v0_1.json`

## Results

### Product-KPI / Operating Metric

- `industry_operating_metric_slot_rows_v0_1`: `1,798` rows / `175` tickers。
- `conflict_resolved_non_aggregate_sibling=411`。
- `unclassified_rejection_count=0`。
- Product/Business-KPI depth：`432/603`，剩余 `171`。
- 剩余 Product-KPI depth gap：
  - `official_product_surface_available_but_company_disclosed_product_kpi_absent=128`
  - `filings_taxonomy_available_but_value_unit_period_product_kpi_absent=42`
  - `product_context_available_but_no_company_disclosed_product_kpi_exact_slot=1`

### CapitalMarketDetail

- `sec_capital_market_event_context_rows_v0_1`: `17,485` rows / `588` tickers。
- Source roles：
  - `beneficial_ownership_filing_event=4,660`
  - `insider_transaction_filing_event=4,636`
  - `proxy_governance_filing_event=4,366`
  - `securities_offering_filing_event=3,823`
- CapitalMarketDetail depth：`587/603`。
- 剩余 `16`：
  - `15` 家非美 / local exchange issuer 需要 local filing / IR / exchange adapter。
  - `FDXF` 为 primary detail/entity parser gap，当前只有 SEC Form 3/4 event metadata。

### ProductRelationshipGraph

- `node_count=8,187`
- `edge_count=25,251`
- `product_slot_count=6,521`
- `parser_backed_relationship_edge_count=741`
- 新增 parser-backed edge split：
  - `OFFICIAL_CUSTOMER_DEPLOYMENT_EVENT=222`
  - `OFFICIAL_SUPPLY_CHAIN_RELATIONSHIP=147`
  - `PUBLIC_ORDER_OR_TENDER_CONTEXT=273`
  - `CHANNEL_OR_DISTRIBUTION_CONTEXT=99`

### Depth Matrix

- `product_spec_depth=603/603`
- `product_kpi_depth=432/603`
- `customer_deployment_depth=387/603`
- `capital_market_detail_depth=587/603`
- `market_liquidity_depth=603/603`
- full five-dimension parity：`279/603`
- remaining backfill queue：`403`
  - CustomerDeployment `216`
  - Product-KPI `171`
  - CapitalMarketDetail `16`

## Boundaries

- SEC submissions metadata rows only prove filing event existence/timing. They do not prove offering amount, security terms, insider shares, beneficial ownership percentage, proxy vote, buyback amount, compensation facts, or realtime fund flow.
- ProductRelationshipGraph edges are provenance-backed context edges. They support retrieval, specialist reasoning, read-through, counterparty/supply-chain context, and bounded thesis drivers. They do not create exact product sales, ASP, sell-through, market share, backlog, or order-value authority.
- Product-KPI exact remains company-disclosed value/unit/period/product/citation only. Industry operating metrics may support operating analysis but must remain separate from hard product revenue / SKU sales exact facts.

## Remaining Work

- Continue CustomerDeployment source locator / browser / PDF / site-specific parser work for the remaining `216` depth gaps.
- Continue Product-KPI source-specific table relation parser work for `42` filings-taxonomy candidates and deep adapter/source-boundary review for `128` official-surface-only companies.
- Add non-US local capital filing / IR / exchange adapters for the `15` non-US CapitalMarketDetail gaps.
- Audit `FDXF` universe/entity mapping and primary detail basis.
- Finish R27 graph consumption/gates: authority/confidence governance, Research Lead / Product Specialist graph reading, and forbidden-claim eval.
- Finish R28 source-specific exact parsers for Form 3/4/5 XML, 13D/13G schedules, offering terms, and proxy/governance tables.

## Verification

Commands run during implementation:

```powershell
python -m pytest tests/test_industry_operating_metric_slot_rows.py -q
python -m pytest tests/test_sec_capital_market_event_context_rows.py -q
python -m pytest tests/test_product_slot_relationship_graph.py -q
python -m py_compile scripts\data_expansion\build_industry_operating_metric_slot_rows.py scripts\data_expansion\build_sec_capital_market_event_context_rows.py scripts\data_expansion\build_product_slot_relationship_graph.py src\sec_agent\product_slot_relationship_graph.py
python scripts\data_expansion\build_industry_operating_metric_slot_rows.py
python scripts\data_expansion\build_sec_capital_market_event_context_rows.py --fetch-missing-submissions --fetch-workers 8 --fetch-limit 200 --user-agent "FINInsightAgent/0.1 research contact noreply@example.com" --request-sleep-seconds 0
python scripts\data_expansion\build_sec_capital_market_event_context_rows.py
python scripts\data_expansion\build_product_slot_relationship_graph.py
python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py
python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py
python scripts\data_expansion\build_second_third_layer_depth_parity_matrix.py
python scripts\data_expansion\build_second_third_layer_depth_gap_action_plan.py
python scripts\data_expansion\build_second_third_layer_real_source_readiness_gate.py
```

Postflight pass:

```powershell
python -m pytest tests/test_industry_operating_metric_slot_rows.py tests/test_sec_capital_market_event_context_rows.py tests/test_product_slot_relationship_graph.py tests/test_second_third_layer_depth_parity_matrix.py tests/test_second_third_layer_depth_gap_action_plan.py tests/test_second_third_layer_real_source_readiness_gate.py -q
python -m py_compile scripts\data_expansion\build_industry_operating_metric_slot_rows.py scripts\data_expansion\build_sec_capital_market_event_context_rows.py scripts\data_expansion\build_product_slot_relationship_graph.py scripts\data_expansion\build_second_third_layer_depth_parity_matrix.py scripts\data_expansion\build_second_third_layer_depth_gap_action_plan.py scripts\data_expansion\build_second_third_layer_real_source_readiness_gate.py src\sec_agent\product_slot_relationship_graph.py
git diff --check
```

Result: `29 passed`; py_compile and diff-check passed.
