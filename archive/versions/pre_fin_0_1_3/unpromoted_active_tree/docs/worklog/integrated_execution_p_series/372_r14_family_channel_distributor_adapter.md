# 372 R14 Step 4 Family Channel / Distributor Adapter

## Prompt

按用户给定 1-6 顺序推进第 4 步：做 channel / distributor family adapters。要求半导体元器件优先走 Digi-Key / Mouser / Arrow 这类渠道方向，消费/零售走 Amazon / JD / official store，工业设备走 distributor / dealer locator；先把能形成 issuer/product-family bound exact-slot context 的 row 真实跑出来，不能提权的写明 attempt-backed gap。

## Decision

本步不把公开渠道页写成价格、库存、sell-through、销量、收入或市场份额事实。新增的可提权对象是 `public_channel_distributor_locator`：它只能证明官方或 issuer-linked 页面存在某种 channel / distributor / dealer / store locator 关系，用于补充产品/渠道存在性和可得性背景。

关键修复是 target source 不能只看当前 `company_gap_docket_v0_1.jsonl`。已经修好的 ticker 会从 docket 里消失，如果 `--replace-output` 时只读 docket，就会把成功 rows 清空。因此 builder 现在同时读取 `company_public_source_coverage_matrix_v0_1.jsonl` 作为 channel requirement 目标全集。

## Work Completed

- 新增 `channel_distributor_locator` source route，并在 exact-slot contract 中注册 `public_channel_distributor_locator` slot。
- 新增 `scripts/data_expansion/build_family_channel_distributor_context_rows.py`：
  - 读取 company matrix、gap docket、family assignment、official product surface rows 和 company domain cache。
  - 用 official-domain / issuer-linked seed 抓取 channel / distributor / dealer / store locator 页面。
  - 写出 context rows 与 attempts ledger。
  - 拒绝 blocked/captcha/client challenge/404/redirect-only 页面。
  - 要求正文或 title 有 locator / channel 语义，不能仅凭 URL 路径提权。
- `build_exact_slot_coverage_matrix.py` 纳入 `family_channel_distributor_context_rows_v0_1.jsonl`。
- `build_exact_slot_gap_closeout_ledger.py` 纳入 `family_channel_distributor_attempts_v0_1.jsonl`，并把剩余 channel gap 归因为 `official_channel_distributor_locator_no_bound_channel_row`。
- 更新 19 文档记录 P4 contract、产物、结果、边界和验收。

## Result And Evidence

Real run:

- `target_ticker_count=62`
- `attempt_count=700`
- `row_count=30`
- `new_or_existing_success_ticker_count=19`
- `unmaterialized_ticker_count=43`

Materialized tickers:

`6752.T`, `CAT`, `COST`, `DE`, `DLTR`, `EMR`, `IFX.DE`, `INTC`, `LOW`, `LULU`, `ROST`, `SMCI`, `TGT`, `TJX`, `TSCO`, `ULTA`, `WMT`, `WOLF`, `XPEV`。

Latest exact-slot matrix:

- `exact_by_source_id.channel_distributor_locator=30`
- `exact_by_slot_kind.public_channel_distributor_locator=30`
- `channel_offer_proxy.ready_count=26`
- `channel_offer_proxy.gap_count=36`
- `exact_slot_gap_count=186`

Remaining channel gaps are all attempt-backed:

- `channel_closeout=36`
- `closeout_reason=official_channel_distributor_locator_no_bound_channel_row`

Verification:

- `python -m py_compile scripts\data_expansion\build_family_channel_distributor_context_rows.py scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> pass
- `python scripts\data_expansion\build_family_channel_distributor_context_rows.py --replace-output --strict --workers 12 --timeout-s 8 --max-seeds-per-ticker 12 --max-links-per-seed 6 --max-rows-per-ticker 2` -> `status=pass`
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`
- `python -m pytest tests\test_family_channel_distributor_context_rows.py tests\test_exact_slot_contracts.py tests\test_exact_slot_gap_closeout_ledger.py tests\test_company_gap_docket.py tests\test_product_kpi_deep_gap_diagnostic.py -q` -> `25 passed`

## Follow-Up

- Remaining 36 channel gaps should not be treated as final commercial gaps yet. They need site-specific Playwright / official store / Digi-Key / Mouser / Arrow / Amazon / JD / distributor locator adapters before final boundary closeout.
- Do not use this row class as product revenue, channel inventory, price, ASP, sell-through, unit volume, demand, or market share evidence.
