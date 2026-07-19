# P34 AI/Semis Goldcase 与当前 RAG/Route 可得性对齐 v0.1

本文件用于在 true full-chain eval 前校准 goldcase：不能要求 agent 输出当前 RAG/SQL/Milvus/route 尚未形成 runtime row 的 exact 数据。

## 当前可得性

- Indexed rows: `154484`；tickers: `603`。
- P34 slots: `20/20` attempted；accepted runtime rows: `21`；typed gaps: `2`。
- Analyst fact tables: `7` blocks / `23` rows。
- Value quality: `{'structured_metric_context': 6, 'specific_technical_or_deployment_fact': 8, 'context_summary': 7, 'attempt_backed_gap': 2}`。

## 关键边界

- RAG/Milvus 角色：The current P34 scoped writer case is a source-route/runtime-row replay, not a Milvus/rerank-driven full-chain retrieval run. RAG/Milvus remains the broader discovery and retrieval substrate, but this case intentionally tests whether accepted source-route rows can be made analyst-ready.
- SEC/parser 边界：The issue found here is not that SEC/8-K table parsing is globally broken. Some P34 rows come from official press releases/pages and current live-route adapters still preserve them as context_summary instead of extracting every numeric table cell. Standardized SEC/XBRL/ledger rows remain usable where already materialized, but this scoped case cannot assume numbers not present in accepted runtime rows.

## Goldcase 对齐决策

### Product / architecture judgment

- 当前支撑：Supported by official/spec rows for NVDA GB200 NVL72, AMD MI300X/MI355X, Google TPU and A4X/GB200 deployment surface.
- 允许回答：Can compare product capability, architecture, bandwidth/memory, benchmark proxy and deployment/adoption path.
- 不允许回答：Cannot infer SKU revenue, ASP, shipment, supplier allocation or market share.
- 状态：`supported_with_boundary`

### DELL AI server financial quality

- 当前支撑：Supported for orders/shipments/backlog and ISG baseline visibility, but not AI server gross margin, GPU pass-through, attach rate or backlog conversion.
- 允许回答：Can state demand/revenue visibility is stronger than generic server demand.
- 不允许回答：Cannot conclude AI server growth is high-quality profit until margin bridge rows are parsed or disclosed.
- 状态：`attempt_backed_gap_for_margin_quality`

### Hyperscaler capex read-through

- 当前支撑：Supported as demand-pool context from MSFT/GOOGL/META/AMZN rows.
- 允许回答：Can discuss demand-pool strength and supplier-capture conditions.
- 不允许回答：Cannot turn capex into NVDA/DELL/ASML/LRCX revenue, allocation, backlog or order exact.
- 状态：`supported_context_not_supplier_capture`

### Semicap read-through

- 当前支撑：Supported by TSM/ASML/AMAT/LRCX rows as mechanism context.
- 允许回答：Can separate advanced node, lithography, materials engineering and HBM/process-intensity read-through.
- 不允许回答：Cannot claim AI-specific bookings, backlog, shipments, customer allocation or China exposure exact unless parsed from issuer rows.
- 状态：`supported_with_deeper_parser_boundary`

### Market price-in / capital feedback

- 当前支撑：Only bounded fixture/market context is present in this scoped case.
- 允许回答：Can say recommendation-quality judgment is constrained by missing valuation/positioning/flow evidence.
- 不允许回答：Cannot output buy/sell strength, real-time crowding, complete options positioning, borrow cost or price-in conclusion.
- 状态：`bounded_gap_until_market_pack_runtime_rows_exist`

## 评测体系更新

true full-chain eval 前新增检查：

- Every memo writer payload must include analyst_fact_table_blocks or explicitly explain why the case has no tableable facts.
- Eval must separate retrieval path: SQL/Milvus/RAG, source-route live attempt, existing manifest row, or deterministic fixture.
- Each goldcase required item must map to available/runtime, context_summary, attempt_backed_gap, commercial_gap, or not_in_current_rag_scope.
- Writer output must render fact tables before required-item boundary language.
- A true full-chain eval cannot pass if a goldcase requirement is absent from RAG/route availability but still demanded as exact output.

仍需用户认可后才能执行：

- `true_full_chain_eval`
- `paid_model_comparison`
- `case_expansion_release_eval`
