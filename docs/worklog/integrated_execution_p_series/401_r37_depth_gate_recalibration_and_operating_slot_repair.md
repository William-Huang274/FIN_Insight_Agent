# 401 R37 Depth Gate Recalibration And Operating Slot Repair

## Prompt

用户要求继续解决第二层、第三层数据深度不一致的问题，尤其不能把 parser/source route 漏吃造成的缺口误判为公开源不可得，也不能用弱 proxy、attempt row 或 generic context 填平 depth parity。

## Decision

本轮只修三类可证明的漏接，不改变证据边界：

- CustomerDeployment：允许公司披露的经营 footprint / operating metric rows 进入 customer/deployment depth，但只接受 capacity、production/throughput、shipments、unit deliveries、same-store sales、AUM、orders/backlog 等经营槽位；产品收入或 generic segment revenue 不进入 customer/deployment。
- CapitalMarketDetail：允许非美 L1 财报 rows 中的资产、负债、权益、现金、债务、经营现金流、capex 等 primary capital / working-capital 科目进入 capital depth；收入、毛利、经营利润等普通损益科目不进入 capital depth。
- Product/Business-KPI：继续修 source-specific table relation 的误拒，只把能保留 value/unit/period/product or business segment/citation 的 rows 提权；region-only、percentage/change、conflicting table relation 和 mislabeled revenue rows 不得冒充产品收入。

## Work Completed

### CustomerDeployment Gate

- 更新 `src/sec_agent/layer_acceptance_gates.py`：
  - 把 `industry_operating_metric_slot_rows_v0_1`、`company_reported_product_operating_metric_runtime_rows_v0_1`、`official_business_asset_profile_context_rows_v0_1` 纳入 CustomerDeployment depth source files。
  - 新增 `business_operating_footprint_signal_ready` 状态。
  - 新增 operating footprint gate，只接受经营 footprint source roles，不接受 product revenue / generic segment revenue。
- 更新 `scripts/data_expansion/build_second_third_layer_depth_parity_matrix.py`：
  - 同步 depth matrix 的 CustomerDeployment row sources，避免 runtime gate 和 matrix 统计口径不一致。
- 新增 deterministic tests：
  - 接受公司披露的经营 footprint。
  - 拒绝把 product revenue 当成 customer/deployment footprint。

### CapitalMarketDetail Gate

- 更新 `src/sec_agent/layer_acceptance_gates.py`：
  - 把 `non_us_l1_financial_statement_metric_runtime_rows_v0_1` 纳入 CapitalMarketDetail source files。
  - 新增 `non_us_primary_capital_disclosure_ready` 状态。
  - 只接受 assets、liabilities、equity、cash、debt、borrowings、capital、operating cash flow、capex 等 capital / balance sheet / cash-flow 相关科目。
  - 修复 exact context 过宽问题：非美 generic exact rows 不能因为存在 value/unit/period 就进入 capital depth。
- 更新 `scripts/data_expansion/build_second_third_layer_depth_parity_matrix.py`：
  - 同步 CapitalMarketDetail row sources。
- 新增 deterministic test：
  - 非美 primary capital disclosure 可以在没有 SEC capital-event route 时满足 capital detail。

### Product/Business-KPI Operating Slot Repair

- 更新 `scripts/data_expansion/build_industry_operating_metric_slot_rows.py`：
  - 允许 `Segment Orders` 在 segment / order context 下作为 bounded `backlog_or_orders`。
  - 对 `Other sales` 只在文本证明为 major customer type revenue disaggregation 时作为 `business_segment_revenue`；generic `other` 继续拒绝。
  - 修复 CVNA 类 `Retail units sold` 被上游误标为 `product_revenue` / USD thousands 的情况：按 raw text 和 row/product label 重写为 `unit_sales_or_deliveries`，单位转为 `units`，并保留 source value/unit 作为 provenance。
- 新增 deterministic tests：
  - `Segment Orders` bounded backlog/order slot。
  - customer-type `Other sales` disaggregation 不是 generic other。
  - mislabeled product revenue units sold 修正为 unit-sales slot。

## Current Metrics

R37 重建后的 `second_third_layer_depth_parity_summary_v0_1`：

- ProductSpec/Profile depth：`603/603`
- Product/Business-KPI depth：`434/603`
- CustomerDeployment depth：`410/603`
- CapitalMarketDetail depth：`601/603`
- MarketLiquidity depth：`603/603`
- Full five-dimension parity：`306/603`
- Remaining backfill queue：`364`

相对 R36：

- Product/Business-KPI：`432 -> 434`
- CustomerDeployment：`387 -> 410`
- CapitalMarketDetail：`587 -> 601`
- Full parity：`279 -> 306`
- Backfill queue：`403 -> 364`

## Remaining Gaps

- CustomerDeployment `193`：当前没有可绑定 runtime rows。已有 official deployment / public award / channel / supply-chain attempts 不等于证据；下一步需要真实 materializer 和 site/source-specific parser，而不是 gate 放宽。
- Product/Business-KPI `169`：
  - `128` 是 official product surface 有，但公司披露产品 KPI exact slot 缺失或需要更深 parser。
  - `40` 是 filings taxonomy 有，但 value/unit/period/product KPI 缺失。
  - `1` 是 product context 有但 no exact slot。
  - source-specific table relation gap 仍有 `17`，主要是 region-only、percentage/change、冲突 column group 或 missing table coordinate。
- CapitalMarketDetail `2`：
  - `6723.T` Renesas：当前非美 L1 只抽到 revenue / gross profit / operating profit / profit attributable，缺 balance sheet / cash-flow / capital detail parser。
  - `FDXF`：只有 SEC Form 3/4 metadata 和 parent-segment operating income；作为子实体不能自动继承 parent FDX capital detail，需 parent-child capital inheritance policy 或暴露 entity boundary gap。

## Validation

- `python -m pytest tests/test_second_third_layer_depth_parity_matrix.py tests/test_industry_operating_metric_slot_rows.py tests/test_second_third_layer_depth_gap_action_plan.py tests/test_second_third_layer_real_source_readiness_gate.py -q` -> `26 passed`
- `python -m py_compile src\sec_agent\layer_acceptance_gates.py scripts\data_expansion\build_second_third_layer_depth_parity_matrix.py scripts\data_expansion\build_industry_operating_metric_slot_rows.py scripts\data_expansion\build_second_third_layer_depth_gap_action_plan.py scripts\data_expansion\build_second_third_layer_real_source_readiness_gate.py` -> pass
- `python scripts\data_expansion\build_second_third_layer_depth_parity_matrix.py` -> pass
- `python scripts\data_expansion\build_second_third_layer_depth_gap_action_plan.py` -> pass
- `python scripts\data_expansion\build_second_third_layer_real_source_readiness_gate.py` -> pass
