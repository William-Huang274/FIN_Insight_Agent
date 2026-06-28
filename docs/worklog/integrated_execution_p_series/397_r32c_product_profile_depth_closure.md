# 397 R32c Product Profile Depth Closure

## 问题

用户要求继续把 600+ 公司第二层/第三层数据做成同等深度，不能只落骨架或用弱 fallback 掩盖缺口。R33 后 ProductSpec/Profile depth 仍只有 `53/603`，主要短板已经从“有没有 URL”变成“是否有 parser-backed、公司可绑定、能被 Product/Technology specialist 使用的产品/业务 profile rows”。

## 判断

不能把普通 product page、generic taxonomy、region/total/revenue rows 硬提权成 SKU revenue、ASP、销量、份额、sell-through、backlog 或订单金额。但对于投研报告，确认公司真实产品、业务线、服务形态、资产/经营足迹本身是有价值的第二层事实底座，应作为 bounded profile context 进入 evidence flow，供 Research Lead 和 Product Specialist 做产品/业务面判断。

因此本轮不继续放宽 `technical_product_spec`，而是新增 bounded profile contract：

- `ProductProfileSlot`
- `BusinessProfileSlot`

并新增 source roles：

- `official_product_profile_spec`
- `business_service_profile_spec`

## 已完成

- 新增 `scripts/data_expansion/build_company_disclosed_product_profile_context_rows.py`。
- 生成 `data/manifests/company_disclosed_product_profile_context_rows_v0_1.jsonl` 和 summary。
- 将新 profile rows 接入：
  - `src/sec_agent/layer_acceptance_gates.py`
  - `src/sec_agent/product_family_source_routes.py`
  - `scripts/data_expansion/build_product_family_source_route_plan.py`
  - `scripts/data_expansion/build_second_third_layer_depth_parity_matrix.py`
- 新增测试 `tests/test_company_disclosed_product_profile_context_rows.py`，并更新 depth parity / route plan 相关测试。
- 更新 23 文档、master checklist 和 worklog README。

## 结果

`company_disclosed_product_profile_context_summary_v0_1`：

- `status=pass`
- `row_count=8,880`
- `ticker_count=603`
- `ProductProfileSlot=8,827`
- `BusinessProfileSlot=53`
- 主要 profile 类型：
  - `company_filing_taxonomy_candidate_profile=4,507`
  - `company_disclosed_product_or_segment_metric_profile=2,009`
  - `sec_filings_product_taxonomy_profile=1,815`
  - `official_product_catalog_profile=337`
  - `official_product_surface_category_profile=148`

`second_third_layer_depth_parity_summary_v0_1`：

- `product_spec_depth=603/603`
- `product_kpi_depth=400/603`
- `customer_deployment_depth=158/603`
- `capital_market_detail_depth=247/603`
- `market_liquidity_depth=603/603`
- full five-dimension parity `52/603`
- backfill queue `1,004`

剩余 gap 已不再包含 ProductSpec/Profile，主要是：

- Product/Business-KPI exact：`203`
- CustomerDeployment：`445`
- CapitalMarketDetail：`356`

## 边界

本轮 profile rows 只支持产品/业务/服务/资产 profile 分析。它们不能被写成：

- 产品收入、SKU revenue
- ASP、销量、出货量
- 市占率、sell-through
- 库存、backlog
- 客户订单金额
- commercial tracker exact facts

`company_filing_taxonomy_candidate_profile` 是 candidate-backed bounded row，适合做 Research Lead 的方向规划和 Product Specialist 的产品面补全，不适合直接作为 memo 中的高强度产品财务 claim。

## 验收

- `python -m pytest tests/test_company_disclosed_product_profile_context_rows.py tests/test_second_third_layer_depth_parity_matrix.py tests/test_product_family_source_routes.py -q`
- `python -m py_compile scripts/data_expansion/build_company_disclosed_product_profile_context_rows.py scripts/data_expansion/build_second_third_layer_depth_parity_matrix.py scripts/data_expansion/build_product_family_source_route_plan.py src/sec_agent/layer_acceptance_gates.py src/sec_agent/product_family_source_routes.py`
- `git diff --check`

## 下一步

1. R35 Product/Business-KPI exact：优先处理 `203` 个剩余缺口，区分 public-source boundary、company-disclosed exact、industry operating metric slot 和 parser/join bug。
2. R33 CustomerDeployment：补官方客户部署、订单、供应链官方关系、公开采购、cloud/OEM deployment proxy。
3. R34 CapitalMarketDetail：补 offering terms、Form 3/4/5 XML、13D/13G schedule、proxy/buyback/governance、short interest/options/ETF/credit-spread 等 source-specific parsers。
