# 402 R38 Second / Third Layer Depth Payment Growth And Boundary Closeout

## 问题

用户要求继续解决第二层、第三层数据深度的三个瓶颈：Product-KPI exact、CustomerDeployment / external validation、CapitalMarketDetail，不能用弱兜底隐藏缺口。R37 后 depth matrix 为 Product/Business-KPI `434/603`、CustomerDeployment `410/603`、CapitalMarketDetail `601/603`、full parity `306/603`，仍有 `364` 条 backfill queue。

## 决策

- 只提权公司披露、带 value / unit / period / citation 的 exact 或 bounded operating rows。
- 不把普通 product revenue、business segment revenue、macro bridge、generic CompanyFacts revenue/AR/inventory 或 attempts rows 当作 customer/deployment。
- 不把 FDXF 直接继承 FDX 母公司资本结构；不把 Renesas 普通利润表行当成资本细项。
- 对上游误标为 `product_revenue` 的支付平台经营指标和 segment revenue growth 做 source-specific repair，但保留 forbidden claims。

## 完成

- `scripts/data_expansion/build_industry_operating_metric_slot_rows.py`
  - 新增 payment activity repair：
    - `payment_transactions_per_active_account`
    - `tpv_mix_percent`
    - `total_payment_volume`
    - `processed_transactions`
  - 新增 `segment_revenue_growth` repair，接受 `percentage_or_change` 与窄范围 `sentence_relation_insufficient` 行，但排除税率、FX、acquisition/divestiture、constant currency、纯地域等假阳性。
  - 继续保留 period-column binding guard，防止 header/scale 列被提权。
- `src/sec_agent/layer_acceptance_gates.py`
  - Product/Business-KPI depth 接受新增 payment / revenue-growth exact slot。
  - CustomerDeployment 只接受真实 customer/order/deployment、channel/adoption、regulated identity、contract-liability、operating-footprint rows；未把 `segment_revenue_growth` 加入 customer gate。
- `tests/test_industry_operating_metric_slot_rows.py`
  - 增加 payment activity、TPV mix、segment revenue growth 的 deterministic tests。

## 结果

- `industry_operating_metric_slot_rows_v0_1`
  - `1,866` rows / `187` tickers。
  - 新增/确认 slot：`payment_transactions_per_active_account=5`、`tpv_mix_percent=8`、`segment_revenue_growth=34`。
  - `unclassified_rejection_count=0`。
- 最新 depth matrix：
  - ProductSpec/Profile：`603/603`
  - Product/Business-KPI：`442/603`
  - CustomerDeployment：`531/603`
  - CapitalMarketDetail：`601/603`
  - MarketLiquidity：`603/603`
  - full five-dimension parity：`399/603`
- 最新 backfill queue：`235`
  - Product-KPI：`161`
  - CustomerDeployment：`72`
  - CapitalMarketDetail：`2`

## 剩余边界

- Product-KPI `161`：
  - `123` 为 official product surface 可得但公司未披露 product KPI exact。
  - `37` 为 filings taxonomy 有产品/业务线方向但 value/unit/period/product relation 仍缺或不能安全提权。
  - `1` 为 product context 有但 exact slot 缺失。
- CustomerDeployment `72`：
  - 每家公司至少有财务或宏观/官方 context rows，但没有可绑定的 customer/order/deployment/channel/adoption/regulated/contract-liability/operating-footprint rows。
  - 普通 revenue from contracts with customers、segment revenue、macro official bridge 不提权。
- CapitalMarketDetail `2`：
  - `6723.T` Renesas 当前只有非美 IR 利润表行，缺 BS/CF/debt/capex/ownership/filing-event 资本细项。
  - `FDXF` 只有 Form 4 metadata 与母公司 segment operating income，不能直接继承 FDX 母公司资本结构。

## 验证

- `python -m pytest tests/test_industry_operating_metric_slot_rows.py tests/test_second_third_layer_depth_parity_matrix.py tests/test_second_third_layer_depth_gap_action_plan.py tests/test_second_third_layer_real_source_readiness_gate.py -q`
  - `35 passed`
- `python -m py_compile scripts/data_expansion/build_industry_operating_metric_slot_rows.py scripts/data_expansion/build_second_third_layer_depth_parity_matrix.py scripts/data_expansion/build_second_third_layer_depth_gap_action_plan.py scripts/data_expansion/build_second_third_layer_real_source_readiness_gate.py src/sec_agent/layer_acceptance_gates.py`
  - pass
- `python scripts/data_expansion/build_second_third_layer_real_source_readiness_gate.py`
  - pass：`603/603` companies have second-layer actual parser source and third-layer actual parser source.

## 后续

- Product-KPI 剩余 `source_specific_table_relation_parser_gap=14` 需要逐公司检查是否存在可安全解析的表格；IR 的 segment orders 当前冲突是 segment label 丢失，不能直接提权。
- CustomerDeployment 剩余 `72` 需要继续走 company-specific official customer/case/channel/contract/regulatory/operating footprint locator；如果公开源确无，就暴露为 public-source/commercial/manual-primary-research gap。
- Capital 两个剩余不应由 parent inheritance 或 ordinary income statement fallback 隐藏，除非后续补到 Renesas annual securities report BS/CF/capital tables 或 FDXF standalone capital filings。
