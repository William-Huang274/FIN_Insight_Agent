# 411 R42 RD4 Research Graph Store

## Problem

RD3 已把 600+ 公司 financial / product / customer / capital / market / macro / source-authority rows 统一成 Gold Fact / Signal Mart，但 Research Lead 和 specialist 还需要“公司、产品、客户、供应链、竞争、资本、市场”之间的图关系，而不是只查行表。RD4 的目标是把现有 ProductRelationshipGraph 和 Gold Mart rows 升级为可 SQL 查询、可证据追溯的 graph store。

## Decision

RD4 合并两类来源：

- 现有 `product_relationship_graph_nodes_v0_1.jsonl` / `product_relationship_graph_edges_v0_1.jsonl`。
- RD3 `gold_fact_signal_mart_rows_v0_1.jsonl`。

输出三类对象：

- `research_graph_nodes`: company、product family、product slot、product context、counterparty、fact/signal type。
- `research_graph_edges`: 产品/产品族/竞争/上下游/客户部署/财务/产品 KPI/资本/市场/宏观/source-authority 等边。
- `research_graph_evidence_support`: 每条边的 Gold row 或 source evidence ref 支持。

图边不新增事实提权；authority 继承 RD3 Gold Mart 或 ProductRelationshipGraph 原边界。

## Work Completed

- 新增 `src/sec_agent/research_graph_store.py`。
- 新增 `scripts/data_expansion/build_research_graph_store.py`。
- 新增 `tests/test_research_graph_store.py`。
- 物化：
  - `data/manifests/research_graph_nodes_v0_1.jsonl`
  - `data/manifests/research_graph_edges_v0_1.jsonl`
  - `data/manifests/research_graph_evidence_support_v0_1.jsonl`
  - `data/manifests/research_graph_summary_v0_1.json`
  - `data/workbench_private/research_data/research_graph_store_v0_1.sqlite`
  - `docs/internal/vnext_20260610/rd4_research_graph_store.zh-CN.md`
- 更新 `docs/architecture/agent_graph_vnext/24_raw_disclosure_rag_database_recap_and_data_base_plan.zh-CN.md`。
- 更新 `docs/worklog/00_internal_master_checklist.md` 与 `docs/worklog/README.md`。

## Result

最新真实构建结果：

- status: `pass`
- nodes: `26,538`
- edges: `100,145`
- evidence support rows: `113,199`
- dangling edges: `0`
- unsupported edges: `0`
- SQLite parity: nodes `26,538` / edges `100,145` / support `113,199`
- exact authority edges: `30,722`
- bounded thesis-driver edges: `69,333`
- planning / gap-only edges: `90`

关键 edge type：

- `HAS_FINANCIAL_STATEMENT_FACT`: `15,849`
- `HAS_PRODUCT_KPI_FACT`: `7,455`
- `HAS_PRODUCT_PROFILE_OR_SPEC`: `16,292`
- `HAS_CUSTOMER_DEPLOYMENT_OR_ORDER_SIGNAL`: `370`
- `HAS_CAPITAL_FUNDING_OWNERSHIP_FACT`: `25,055`
- `HAS_MARKET_LIQUIDITY_SIGNAL`: `603`
- `HAS_SOURCE_AUTHORITY_ROW`: `7,181`
- ProductRelationshipGraph 原边：`25,251`

真实构建中暴露并修复：

- `140` 条 no-ticker Gold Mart rows 生成 dangling `unknown_issuer` 起点。修复为创建 `unknown_issuer` 节点，保留原 row，不跳过。
- `3,597` 条 ProductRelationshipGraph 原边缺 evidence_ref。审计后 `3,532` 条是 `HAS_PRODUCT_SLOT` / `FAMILY_HAS_PRODUCT_SLOT` 结构性 taxonomy 边，标为 `structural_graph_topology_no_external_ref`；`65` 条 production/dependency/modelled relationship 缺 direct evidence_ref，降为 `planning_or_gap_only`，不进入 evidence bundle。

## Verification

- `python -m pytest tests/test_research_graph_store.py -q` -> `3 passed`
- `python -m py_compile src/sec_agent/research_graph_store.py scripts/data_expansion/build_research_graph_store.py` -> pass
- `python scripts/data_expansion/build_research_graph_store.py` -> `pass`

## Boundary And Follow-up

- `source_evidence_ref_only` 表示 ProductRelationshipGraph 原边有 evidence ref，但未映射到 RD3 Gold row；仍保持原图边 claim boundary。
- `structural_graph_topology_no_external_ref` 只能支持 taxonomy/topology navigation，不能单独支撑经营结论。
- `modelled_relationship_without_direct_evidence_ref` 已被降为 planning/gap-only；后续如果要提权，必须补 source-specific evidence row 或 Gold Mart support。
- RD5 需要把 BM25/ObjectBM25/SQLite FTS/Milvus retrieval hit 回连到 RD1/RD2/RD3/RD4 主账本。
