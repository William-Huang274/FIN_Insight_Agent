# 362 R12 Product-Family Gap Repair Browser Ladder

## Prompt

用户确认 26 条公开源 gap 如果覆盖公司较多就必须继续修，并明确允许使用 Playwright 或更真实的浏览器渲染抓取公开页面。边界是不攻击网站、不绕过登录/验证码/资质，只做正常公开页面、sitemap、IR、PDF/catalog 等可公开访问内容的抓取和解析。

## Decision

把原 `product_family_runtime_gap_closeout_v0_1` 的 26 条从“最终 gap”降级为 repair 输入，新增可审计 `repair ladder`：

- `repair_required`：还没走完公开源修复阶梯。
- `adapter_needed_not_final_gap`：已经尝试了部分公开源，但缺 browser/parser/local regulator/L2-L3/family-binding repair，不能 final closeout。
- `fixed_to_runtime_row`：重建 product graph 后，目标 ticker-family 已变成 runtime-ready slot。

默认不允许输出 `public_source_exhausted_gap`。只有官网/浏览器、PDF/catalog、当地交易所/监管、L2/L3 family route、family-binding repair 全部走完并有审计记录，才允许最终 closeout。

## Work Completed

- 新增 `src/sec_agent/product_family_gap_repair.py`：
  - repair ladder schema；
  - 逐 ticker-family repair state 判定；
  - `final_gap_allowed_count` hard gate；
  - 缺步骤审计。
- 新增 `scripts/data_expansion/repair_product_family_runtime_gaps.py`：
  - 输入原 26 条 closeout；
  - 生成 family official product surface profiles；
  - HTTP-first，blocked/non-content 时走 browser-backed fetch；
  - 重建 official product surface context rows；
  - 重建 product slots / relationship graph；
  - 写出 repair ledger 和 summary。
- 更新 `scripts/data_expansion/materialize_official_product_surface_pages.py`：
  - `PlaywrightBrowserFetcher`；
  - `HttpThenBrowserFetcher`；
  - 自动探测本机 Chrome / Edge，也支持 `FINSIGHT_BROWSER_EXECUTABLE_PATH`。
- 新增 `tests/test_product_family_gap_repair.py`：
  - 未走完 ladder 的 row 不能 final closeout；
  - 修复后可进入 runtime-ready product slot。

## Run And Results

正式命令：

```powershell
python scripts\data_expansion\repair_product_family_runtime_gaps.py --max-urls-per-issuer 6 --timeout-s 10
```

产物：

- `data/manifests/product_family_runtime_gap_repair_ledger_v0_1.jsonl`
- `data/manifests/product_family_runtime_gap_repair_summary_v0_1.json`
- `data/manifests/official_product_surface_context_rows_v0_1.jsonl`
- `data/manifests/company_product_slots_v0_1.jsonl`
- `data/manifests/product_relationship_graph_summary_v0_1.json`
- `Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/company_product_pages/company_product_pages.materialized.jsonl`

核心指标：

- 输入原 closeout rows: `26`
- 第一轮 fetch attempts: `144`，new materialized official pages: `38`
- 后续 targeted repair 修复 URL 截断、subdomain 生成、taxonomy whitelist、LLY oncology 官方路由后，materialized official pages: `891`
- official product surface context rows: `2,131`
- materialized ticker count: `432`
- product slots: `6,454`
- family-bound runtime slots: `6,454`
- product graph edges: `24,237`
- repair state:
  - `fixed_to_runtime_row=26`
  - `adapter_needed_not_final_gap=0`
  - `final_gap_allowed_count=0`

已修成 runtime-ready 的 ticker-family：

- `2317.TW / electronics_manufacturing_services`
- `3231.TW / electronics_manufacturing_services`
- `2382.TW / electronics_manufacturing_services`
- `AEE / regulated_utility_power`
- `BHP / mining_materials_commodities`
- `C / banking_credit_deposits`
- `C / capital_markets_trading`
- `CAH / healthcare_distribution_services`
- `CSGP / real_estate_data_marketplace`
- `DIOD / analog_embedded_semiconductors`
- `DIOD / power_semiconductor_components`
- `FANG / upstream_oil_gas`
- `FDXF / logistics_transportation`
- `INTC / gpu_accelerator`
- `INVH / real_estate_infrastructure_reit`
- `LLY / oncology_immunology`
- `LVS / lodging_resorts_cruise`
- `LULU / apparel_athletic_retail`
- `META / ai_platform`
- `MPWR / power_semiconductor_components`
- `NIO / ev_vehicle_platform`
- `ORLY / auto_aftermarket_retail`
- `PSKY / digital_media_content`
- `TEL / connectivity_semiconductor_components`
- `TSLA / battery_charging_autonomy`
- `UHS / healthcare_facilities_services`

当前 26 行没有 remaining repair row。`product_family_runtime_gap_closeout_v0_1` 仍保留旧 closeout 视图，runtime 和 Research Lead 必须以 `product_family_runtime_gap_repair_ledger_v0_1` 为准。

## Verification

```powershell
python -m py_compile scripts\data_expansion\materialize_official_product_surface_pages.py scripts\data_expansion\repair_product_family_runtime_gaps.py src\sec_agent\product_family_gap_repair.py
python -m pytest tests\test_product_family_gap_repair.py tests\test_official_product_surface_materializer.py tests\test_family_official_product_surface_materializer.py tests\test_product_slot_relationship_graph.py -q
```

Result: `21 passed`; ledger sanity audit confirms `26/26` rows are `fixed_to_runtime_row`, `missing_ladder_rows=0`, and `final_gap_allowed_count=0`.

## Follow-up

- Full-chain runtime integration should read `product_family_runtime_gap_repair_ledger_v0_1` rather than treating the old closeout file as final.
- Fixed rows are bounded official surface context only; they do not authorize sales, share, ASP, sell-through, inventory, or undisclosed product KPI claims.
- Remaining product-performance gaps should now be expressed as commercial tracker / company-undisclosed KPI gaps, not as missing official surface/parser rows for this 26-row tranche.
