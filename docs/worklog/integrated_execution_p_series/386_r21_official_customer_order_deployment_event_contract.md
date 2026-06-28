# 386 R21b Official Customer Order Deployment Event Contract

## Prompt

用户指出旧 `public_order_proxy` 口径不应继续把公司官方公告里的客户、订单、项目、部署、供应关系都塞进 public-order exact，而应该新增或拆分一个更合理的合同，例如 `official_customer_order_or_deployment_event`。该合同允许公司官方公告里的订单金额、项目规模、客户、产品、日期作为官方事件 fact，但仍要与公开采购 award exact、收入 exact、backlog exact 分开。

## Decision

本轮采用收紧口径，而不是继续扩大 `public_order_proxy`：

- `public_order_proxy` 只代表公开采购、tender、award、政府合同或等价公开采购 snapshot，不能由 generic supplier/customer relationship 自动满足。
- `official_customer_order_or_deployment_event` 作为独立 source role / exact-slot contract / route contract / signal authority，支撑官方客户、订单、部署、项目、协议事件。
- 事件合同只允许 bounded thesis driver：customer deployment、demand context、official relationship validation、verification lead。禁止 revenue、backlog、ASP、shipment、sell-through、market share、complete order book。

## Work Completed

- `src/sec_agent/exact_slot_contracts.py`
  - 新增 `official_customer_order_or_deployment_event` contract。
  - 新增 event row verifier，要求 issuer / counterparty / product 或 segment / event signal 绑定。
  - 保留 `public_order_proxy` exact gap，不用 event row 冒充 award exact。
- `scripts/data_expansion/build_targeted_supply_chain_official_relationship_rows.py`
  - 输出 `source_role`、`relationship_label`、`event_type`、`event_date`、`event_scale_text`。
  - 只有明确 customer order / agreement / deployment / project / production 等事件文本进入 event role。
- `src/sec_agent/source_coverage_gate.py`
  - 新增 `official_customer_order_or_deployment_event` requirement template。
  - `public_order_proxy` source ids 收紧回 `public_tenders_contracts_orders`。
  - 修复 schema 对齐：`official_product_surface` 接受 `sec_product_taxonomy_normalized`，`regulated_product_context` 接受 `fda_animal_drugs_api`，强绑定白名单增加 subsidiary / macro bridge / family assignment context。
- `src/sec_agent/company_public_source_coverage_matrix.py`
  - issuer binding 白名单补 `issuer_subsidiary_official_domain_bound`。
- `src/sec_agent/product_family_source_routes.py`
  - 新增 event route，并只在 runtime event row 存在时动态注入 family route plan。
  - 同步 `official_product_surface` 与 `regulated_product_context` source ids。
- `src/sec_agent/non_financial_signal_authority.py`
  - 新增 official customer/order/deployment event 信号 authority。
- `src/sec_agent/source_route_registry_v2.py`
  - 新增 `official_customer_order_or_deployment_event` route contract。
- `scripts/data_expansion/build_r18_data_source_admission_ledger.py`
  - 新 source role 纳入 company-specific requirement 和 support surface。
- `scripts/data_expansion/build_r18_vertical_source_route_gate.py`
  - `public_order_proxy` 只接受 event role 作为更精确 alternate；generic `supply_chain_official_relationship` 不再满足 public-order gate。
  - 审计字段补 `requirement_id`，避免后续 dashboard / CLI 按 requirement 查询时得到空值。

## Result

- Targeted tests:
  - `64 passed`
- Rebuild artifacts:
  - `family_source_route_plan_v0_1.jsonl`
  - `company_public_source_coverage_matrix_v0_1.json/jsonl`
  - `exact_slot_coverage_matrix_v0_1.json/jsonl`
  - `r18_data_source_admission_ledger_v0_1.jsonl`
  - `r18_source_route_registry_v2.json`
  - `r18_source_authority_data_mart_rows_v0_1.jsonl`
  - `r18_vertical_source_route_gate_rows_v0_1.jsonl`
- Latest metrics:
  - Company/source matrix: `603` companies, `578` pass, `25` gap, all `source_gap` for `public_order_proxy`.
  - Exact slot matrix: `official_customer_order_or_deployment_event.ready_count=26`; `public_order_proxy.gap_count=25`.
  - R18 admission ledger: strict pass, `row_count=3,712`.
  - R18 source authority data mart: strict pass, `row_count=3,712`.
  - R18 vertical source-route gate: `600/603` pass; `3` action-required companies.

## Remaining Boundary

Action-required tickers:

- `2382.TW`: current row is official relationship / directory context, not an event fact. Needs Taiwan/local customer award, company IR project/order disclosure, or customer deployment row before it can satisfy public-order / event gate.
- `CRDO`: current relationship context is not an order/deployment/project event. Needs issuer/customer announcement, procurement row, or official deployment case.
- `DNN`: current source is not a public procurement award or official customer/deployment event. Needs jurisdiction tender, regulator/project award, or issuer/customer official event.

These are not hidden fallback rows. They remain source-route/parser/source gaps until a public source can produce exact event or public-order fields.

## Next Step

Proceed to the second layer from 23 document:

- Product spec slots by industry: GPU, CPU, server, semicap, auto, SaaS, medtech, etc.
- Product relationship graph: competition, substitution, upstream/downstream, customer deployment, supply-chain read-through.
- Strong signal sources: benchmark, official customer deployment, cloud instance availability, OEM config, supplier/customer official news, technical whitepaper/docs.

Then proceed to the third layer:

- Capital / funding / ownership / market-liquidity source contracts and runtime rows.
