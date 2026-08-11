# 361 R12 Company Product Slot / Relationship Graph Closeout

日期：2026-06-18

## Prompt

用户要求不要停在“600+ 公司有 lane / route plan”的半成品，而是继续把：

- 各家公司产品抽成细分槽位，并让槽位有真实可接的数据源；
- 建立公司、产品、竞争、上下游关系图谱；
- 对所有公司按规划路线跑完，不能用弱 fallback 隐藏缺口。

## Decision

本轮不通过放宽 matcher 清零 gap。执行口径是：

1. 能通过官方产品页、公司官网、官方 sitemap、IR/官方页面真实抓取并解析的，转成 parser-backed runtime row。
2. 能通过 SEC taxonomy / company-disclosed KPI / official product surface / L2-L3 bounded source 绑定 family 的，进入 product slot graph。
3. 只有同 family 且 relationship-ready 的 company-family node 生成 `COMPETES_WITH` candidate edge。
4. 供应链上下游边只使用预定义 family template + route refs，全部标为 analyst-context edge，不代表订单、收入、份额或客户集中度。
5. 官方站点 403 / bot challenge / 429 / HTTP 567 / timeout，或已有 row 只是公司级、宏观级、车型级、open research proxy 的，写入 closeout gap，不提权。

## Work Completed

- 扩展 `ProductFamilyLaneRegistry`：
  - 新增/修正 `analog_embedded_semiconductors`、`real_estate_data_marketplace`、`farm_ranch_rural_retail` 等细分 family。
  - 修复 TSCO 从错误 `auto_aftermarket_retail` 改到 `farm_ranch_rural_retail`。
  - 修复 CSGP 从粗粒度 REIT 改到 `real_estate_data_marketplace`。
  - 给 META/PSKY digital media family 补 Facebook / Instagram / WhatsApp / Paramount+ / CBS / Nickelodeon aliases。
- 扩展 official product surface materializer：
  - 增加 BYD、DISCO、Panasonic Industrial、ENLT、ESS、INTU、MSFT、PLTR、SWKS、TTWO、TSCO 等 domain/path hints。
  - 修复 ticker override 优先于通用 blocked-domain filter；否则 MSFT 的 `microsoft.com` 会被错误 prune。
  - 把 `Just a moment...` 归类为 blocked/non-content page。
- 完成真实 materialization / graph rebuild：
  - `materialize_family_official_product_surface_pages.py` targeted runs；
  - `build_product_family_source_route_plan.py`；
  - `build_product_slot_relationship_graph.py`。
- 生成 closeout manifest：
  - `data/manifests/product_family_runtime_gap_closeout_v0_1.jsonl`；
  - `data/manifests/product_family_runtime_gap_closeout_summary_v0_1.json`。

## Result

最新 product graph：

- `company_count=603`
- `family_count=81`
- `product_slot_count=6,442`
- `with_family_bound_runtime_slot_count=6,416`
- `official_surface_slot=4,409`
- `filings_taxonomy_slot=1,884`
- `product_kpi_exact_slot=114`
- `bounded_context_slot=9`
- `seed_needs_locator=22`
- `company_route_needs_family_binding=4`
- `edge_count=23,963`
- `COMPETES_WITH=3,133`

Closeout：

- `closeout_row_count=26`
- `bounded_public_gap=22`
- `not_promotable_context_gap=4`

典型剩余边界：

- Hon Hai / Quanta / Wistron：official EMS product pages hit timeout / Radware / 403。
- AEE / CSGP / DIOD / INVH / LULU / LVS / ORLY / PSKY / UHS：official site access blocked。
- BHP / CAH / FANG / TEL：official site timeout or unstable from current runtime.
- INTC GPU / LLY oncology / META AI / TSLA battery：有公司级、proxy 或相邻 family row，但不能安全绑定到目标 product family，禁止提权。

## Verification

已在本轮运行：

- `python -m py_compile scripts\data_expansion\materialize_family_official_product_surface_pages.py scripts\data_expansion\materialize_official_product_surface_pages.py src\sec_agent\product_family_source_routes.py`
- `python scripts\data_expansion\build_product_family_source_route_plan.py`
- `python scripts\data_expansion\build_product_slot_relationship_graph.py`

待最终收口前还需运行 targeted pytest / full py_compile / `git diff --check`。

## Follow-up

- Full-chain Research Lead / Product Specialist 需要把 `company_product_slots_v0_1` 和 `product_family_runtime_gap_closeout_v0_1` 作为第一类规划输入。
- Eval 需要防止 `seed_needs_locator` / `company_route_needs_family_binding` 被 Memo Writer 或 Specialist 提权。
- 对剩余 official-site access gaps，后续如果要继续降低 gap，需要引入浏览器渲染/站点专用 adapter/PDF annual report parser；不能用弱 proxy 或新闻泛页冒充官方产品证据。
