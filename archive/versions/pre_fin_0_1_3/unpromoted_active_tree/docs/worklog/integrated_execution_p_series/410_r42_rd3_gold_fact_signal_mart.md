# 410 R42 RD3 Gold Fact / Signal Mart

## Problem

RD0/RD1/RD2 已把数据资产、原始来源血缘、parser/chunk/table/metric 质量纳入账本。下一步需要把分散在 `data/manifests` 的 accepted financial facts、product facts、bounded product/spec/customer signals、capital/ownership/market rows 和 source-authority rows 合成一个 Research Lead / specialist 可查的长期事实与信号主表，同时保留 forbidden-claim 边界。

## Decision

RD3 不改变原始数据 authority，不把 bounded signal 伪装成 exact financial/product KPI。统一 mart row 只做三件事：

- 把分散 rowsets 映射到统一字段：ticker、fact domain、support surface、authority mode、source role、metric/value/unit/period/product/counterparty/event、citation、allowed/forbidden claims、parser status、source row lineage。
- 写出 JSONL 主表，保留 source rowset ledger。
- 同步写 SQLite mirror，便于后续 Research Lead / specialist / eval 用 SQL 查询，而不是扫散装 JSONL。

## Work Completed

- 新增 `src/sec_agent/gold_fact_signal_mart.py`。
- 新增 `scripts/data_expansion/build_gold_fact_signal_mart.py`。
- 新增 `tests/test_gold_fact_signal_mart.py`。
- 物化：
  - `data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl`
  - `data/manifests/gold_fact_signal_mart_source_rowsets_v0_1.jsonl`
  - `data/manifests/gold_fact_signal_mart_summary_v0_1.json`
  - `data/workbench_private/research_data/gold_fact_signal_mart_v0_1.sqlite`
  - `docs/internal/vnext_20260610/rd3_gold_fact_signal_mart.zh-CN.md`
- 更新 `docs/architecture/agent_graph_vnext/24_raw_disclosure_rag_database_recap_and_data_base_plan.zh-CN.md`。
- 更新 `docs/worklog/00_internal_master_checklist.md` 与 `docs/worklog/README.md`。

## Result

最新真实构建结果：

- status: `pass`
- rows: `74,894`
- companies: `603`
- source rowsets: `17`
- missing source rowsets: `0`
- SQLite rows: `74,894`
- exact company fact authority: `30,722`
- bounded thesis driver authority: `44,147`
- planning / gap only: `25`

按 domain：

- `financial_statement_fact`: `15,849`
- `product_kpi_fact`: `7,455`
- `product_profile_or_spec_fact`: `16,292`
- `industry_operating_metric_fact`: `1,923`
- `customer_deployment_or_order_signal`: `370`
- `capital_funding_ownership_fact`: `25,055`
- `market_liquidity_signal`: `603`
- `macro_industry_driver_signal`: `92`
- `regulated_or_official_api_signal`: `74`
- `source_authority`: `7,181`

本轮真实构建暴露一个 authority 口径问题：部分 SEC capital-market event / context rows 没有 `runtime_ready_context` 布尔字段，但有 parser-pass、allowed claims 和 boundary，应该作为 bounded thesis-driver signal，而不是 gap-only。已修复为基于 parser status / allowed claims / claim boundary 的 bounded 推断，同时对 R18 source-authority 中 `can_enter_evidence_bundle=false` 且 `source_gap` 的 `25` 行强制归一为 `planning_or_gap_only`。

## Verification

- `python -m pytest tests/test_gold_fact_signal_mart.py -q` -> `3 passed`
- `python -m py_compile src/sec_agent/gold_fact_signal_mart.py scripts/data_expansion/build_gold_fact_signal_mart.py` -> pass
- `python scripts/data_expansion/build_gold_fact_signal_mart.py` -> `pass`

## Boundary And Follow-up

- `planning_or_gap_only` 行只允许 Research Lead 用于 planning/gap ledger，不能进入 ClaimCard evidence bundle。
- Product spec、customer deployment、market liquidity、macro/context rows 可以支持 thesis driver 和反证线索，但不能冒充 product revenue、unit sales、ASP、market share、sell-through、channel inventory、backlog 或 customer order value exact。
- RD3 SQLite mirror 只是 Gold Mart v0.1 主表；RD4 还要把产品、客户、供应链、资本、市场流动性做成 evidence-backed graph edges。
