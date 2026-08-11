# R43 ProductIntelligence Runtime Wiring

## Problem

`ProductIntelligenceGraph v0.1` 已经把 603 家公司的产品槽位、产品/业务 KPI、规格/profile、客户部署、供应链、竞品关系和 gap ledger 统一为 company pack。但这些 pack 仍停留在 manifest / SQLite 层，Product Specialist 和 Research Lead 还不能稳定消费它们。

本轮目标是把 company pack 接进 runtime，同时保持边界：规格、客户部署、供应链、渠道、竞品信号可作为 bounded thesis-driver，不得冒充产品收入、销量、ASP、份额、sell-through、inventory、backlog、order value、shipment 或 allocation。

## Decision

- 新增 `product_intelligence_runtime` adapter，把 PIG company pack 转为 runtime context rows。
- `ProductSpecPack` 扩展 `customer_deployment_signals` 和 `supply_chain_signals`，并把 forbidden claims 写入 validation。
- `multi_agent_runtime` 让 Product Specialist / Supply-chain Specialist 在显式 pack 或 `product_intelligence_runtime_autoload=true` 时消费 PIG rows。
- `specialist_llm` 的 known refs / repair payload 允许引用新增 deployment / supply-chain rows。
- `supervising_analyst` 的 `product_bridge_pack` 消费 PIG exact KPI、official product context、customer deployment context 和 product relationship context。
- 默认不盲目 autoload 本地全量 PIG DB，避免普通单测或旧状态按 ticker 被真实库污染；全链路 runtime 可显式打开 autoload。

## Work Completed

- 新增 `src/sec_agent/product_intelligence_runtime.py`。
- 更新：
  - `src/sec_agent/product_spec_pack.py`
  - `src/sec_agent/multi_agent_runtime.py`
  - `src/sec_agent/specialist_llm.py`
  - `src/sec_agent/supervising_analyst.py`
  - `tests/test_product_spec_pack.py`
  - `tests/test_supervising_analyst_pack.py`
- 更新 24 文档、master checklist 和 worklog README。

## Result And Evidence

Deterministic tests:

- `python -m py_compile src/sec_agent/product_intelligence_runtime.py src/sec_agent/product_spec_pack.py src/sec_agent/multi_agent_runtime.py src/sec_agent/specialist_llm.py src/sec_agent/supervising_analyst.py`
- `python -m pytest tests/test_product_intelligence_graph.py tests/test_product_spec_pack.py tests/test_supervising_analyst_pack.py tests/test_multi_agent_specialist_llm.py tests/test_data_quality_release_eval_gate.py -q`
- Result: `63 passed`.

Real-pack smoke:

- `NVDA` with `product_intelligence_runtime_autoload=true`:
  - PIG rows loaded: `45`
  - ProductSpecPack status: `pass`
  - customer deployment signals: `5`
  - supply-chain signals: `3`
  - competitive comparable edges: `1`
  - Research Lead product bridge coverage: product intelligence graph / technical context / customer deployment / supply-chain / competitive context all `true`.
- `000660.KS` with `product_intelligence_runtime_autoload=true`:
  - PIG rows loaded: `39`
  - ProductSpecPack status: `pass`
  - product KPI refs: `2`
  - supply-chain signals: `3`
  - competitive comparable edges: `2`
  - Research Lead product bridge company KPI count: `2`.

## Follow-Up

- Full-chain graph should set `product_intelligence_runtime_autoload=true` only after Research Lead has selected product/technology lanes or loaded explicit company packs from RD6/RD4.
- Memo Writer must continue to consume PIG through Research Lead / MemoLogicPlan; raw PIG rows should not become direct memo prose.
- Remaining quality work is not adapter wiring but source depth: improve product spec values, customer deployment exactness, and commercial tracker gap presentation by industry lane.
