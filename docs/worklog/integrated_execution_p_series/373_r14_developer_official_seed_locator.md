# 373 R14 Developer Official Seed Locator

## Prompt

按 1-6 顺序推进第 5 步：从公司官网 docs / dev pages 找 repo/package seed，再查 GitHub/npm/PyPI/HuggingFace。没有 official seed 的公司继续暴露 resolver gap，不能 blind search 提权。

## Reasoning And Decision

Developer ecosystem rows 之前存在两个风险：

- 搜到 GitHub/npm/PyPI/HuggingFace 并不等于 issuer 官方开发者生态，必须先验证 official seed。
- repo/package 存在只能作为 L3 developer ecosystem proxy，不能支持收入、份额、销量、客户采用率、moat 或产品商业成功判断。

因此本轮采用 official-seed-first 策略：优先扫描公司官方域名、官方 product surface、官方 docs/dev pages；如走 GitHub org/profile，则必须能验证 profile 绑定公司官方域名。找不到 official seed 就写入 resolver gap。

## Work Completed

- 新增 `scripts/data_expansion/build_developer_official_seed_locator.py`。
- 新增 `tests/test_developer_official_seed_locator.py`。
- 更新 `scripts/data_expansion/build_developer_ecosystem_context_rows.py`，接入 located official seed rows。
- 更新 `tests/test_exact_slot_gap_closeout_ledger.py`，防止非 gap ticker 的 materialized developer attempt 被 closeout 重新计成 gap。
- 刷新 developer ecosystem rows、exact-slot matrix、gap closeout、product KPI diagnostic、company gap docket。
- 更新 `docs/architecture/agent_graph_vnext/19_source_role_product_kpi_exact_slot_deep_repair.zh-CN.md`。

## Result And Evidence

Official seed locator real run：

- `target_ticker_count=45`
- `seeded_ticker_count=22`
- `seed_row_count=22`
- `seed_url_count=62`
- `unseeded_ticker_count=23`
- `attempt_count=751`
- `unclassified_target_count=0`

Seeded ticker：

`6723.T`, `ANET`, `APP`, `AVGO`, `CIEN`, `CRDO`, `CTSH`, `FICO`, `FTNT`, `GDDY`, `GEN`, `IFX.DE`, `KEYS`, `MSI`, `ON`, `PTC`, `S`, `STX`, `SWKS`, `TEL`, `TOST`, `VRSN`。

Developer parser materialization：

- `context_row_count=118`
- `parser_backed_row_count=118`
- `ticker_count=62`
- `developer_ecosystem_proxy_requirement.status=pass`
- `entity_bound_row_count=118`
- `product_mentioned_in_snapshot=118`
- `issuer_mentioned_in_snapshot=118`

Exact-slot / docket：

- `developer_ecosystem_proxy.ready_count=62`
- `developer_ecosystem_proxy.gap_count=14`
- `exact_slot_gap_count=171`
- `source_role_gap_docket_count=171`
- `product_kpi_gap_docket_count=377`
- `docket_count=548`
- `unclassified_docket_count=0`

Remaining developer resolver gap ticker：

`APH`, `CDNS`, `CDW`, `COHR`, `DIOD`, `FN`, `GLW`, `IT`, `LITE`, `MTSI`, `Q`, `RMBS`, `ROP`, `WOLF`。

这些剩余项当前缺 verified official docs/repo/package seed 或 official profile/domain binding；不能用第三方 repo、宽泛关键词搜索或非官方镜像提权。

## Verification

- `python -m py_compile scripts\data_expansion\build_developer_official_seed_locator.py scripts\data_expansion\build_developer_ecosystem_context_rows.py scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py` -> pass
- `python scripts\data_expansion\build_developer_official_seed_locator.py --strict --workers 32 --timeout-s 5 --max-source-pages-per-ticker 10 --max-seeds-per-ticker 3 --max-repos-per-org 12` -> pass
- `python scripts\data_expansion\build_developer_ecosystem_context_rows.py --replace-output --strict --timeout-s 10 --fetch-retries 1 --max-rows-per-probe 4` -> pass
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> pass
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> pass
- `python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict` -> pass
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> pass
- `python -m pytest tests\test_developer_official_seed_locator.py tests\test_developer_ecosystem_context_rows.py tests\test_exact_slot_gap_closeout_ledger.py -q` -> `16 passed`

## Follow-up

- 第 6 步继续做 `public_order` / `regulated` / `supply_chain` 小批量专修。
- Developer ecosystem 的剩余 14 家只能在找到 verified official seed 后继续修；否则应暴露 resolver gap。
- L3 developer rows 后续进入 full-chain 时必须保持 L3 proxy 边界，不能被 Memo Writer 或 Specialist 提权成商业结论。
