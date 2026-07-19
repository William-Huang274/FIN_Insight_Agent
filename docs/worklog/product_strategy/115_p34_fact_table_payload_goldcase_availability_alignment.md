# P34 Fact-table Payload / Goldcase Availability Alignment

日期：2026-07-07

## 触发问题

人工 review P34 scoped writer 渲染稿后发现两个根因：

1. writer payload 虽然有 evidence refs、claim 和 required-item answer，但没有把已接受 runtime rows 投影成财务表、产品规格表、客户部署表、市场边界表。最终 memo 容易变成“判断 + 边界说明”，而不是 analyst workpaper。
2. AI/Semis goldcase 如果不先对齐当前 RAG/SQL/Milvus/source-route 可得性，会要求 agent 输出当前 runtime row 尚未提供的 exact 数字，进而把数据源/解析器缺口误判成 writer 或模型问题。

## 本轮修复

- `src/sec_agent/p34_lane_quality_runtime.py`
  - `build_ai_semis_scoped_writer_payload()` 新增 `analyst_fact_table_blocks`。
  - 将 accepted rows 分成 `financial_bridge_table`、`product_spec_architecture_table`、`customer_deployment_oem_table`、`capex_demand_pool_table`、`semicap_readthrough_table`、`market_counter_boundary_table`、`attempt_backed_gap_table`。
  - 将 DELL orders/backlog 这类有经营披露但有 margin boundary 的 row 归为 `structured_metric_context`，避免误标成 gap。
  - 将 market price-in / counter-thesis 这类上下文 row 保持为 `context_summary`，避免误提权。

- `src/sec_agent/langgraph_orchestrator.py`
  - renderer 在 `核心判断` 后插入 `关键数据表`。
  - required-item answer 拆成判断、边界、会改变判断三层，减少一句话里“先判断后免责”的混乱输出。

- `src/sec_agent/memo_llm.py`
  - Memo Writer 不再保留 raw metric id 作为正文表达。
  - 内部字段应翻译成 analyst-readable label，metric id 只允许出现在 evidence ref 或表格审计语境。

- `scripts/eval_multi_agent/run_p34_fact_table_projection_and_goldcase_alignment.py`
  - 新增 no-paid deterministic runner。
  - 生成 deterministic preview 和 goldcase/RAG availability alignment。

## 产物

- `docs/internal/vnext_20260610/p34_fact_table_projection_preview_v0_1.zh-CN.md`
- `docs/project_os/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.json`
- `docs/internal/vnext_20260610/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.zh-CN.md`

## 当前结果

- Indexed rows：`154,484`；tickers：`603`。
- P34 slots：`20/20` attempted；accepted runtime rows：`21`；typed gaps：`2`。
- Analyst fact tables：`7` blocks / `23` rows。
- Value quality：
  - `structured_metric_context=6`
  - `specific_technical_or_deployment_fact=8`
  - `context_summary=7`
  - `attempt_backed_gap=2`

## 重要边界

- 本轮不是 true full-chain，不是 paid LLM rerun，也不是模型对比。
- 本轮不是 Milvus/rerank-driven retrieval run，而是 P34 source-route/runtime-row replay。Milvus/RAG 仍是 broader discovery/retrieval substrate。
- 标准化 SEC/XBRL/CompanyFacts/13F 等材料没有被判定为全局解析失效；本轮问题集中在 AI/Semis live source-route rows，尤其官方 press/product/IR 页面没有全部抽成 numeric table cells。
- 当前 goldcase 已调整为只能要求 runtime availability 支撑的内容：
  - 产品/架构可用 specs、benchmark proxy、official deployment surface 做 bounded 判断。
  - DELL AI server 可以写 orders / shipments / backlog 和 ISG baseline，但不能写 AI server gross margin 已改善。
  - Hyperscaler capex 只能写 demand-pool context，不能直接写供应商订单/收入。
  - Market price-in exact positioning 仍是 bounded/commercial/deeper-adapter gap。

## 验证

- `python -m pytest -q tests/test_p34_scoped_memo_writer_payload.py tests/test_p33_memo_projection_replay.py`
  - `8 passed`
- `python scripts/eval_multi_agent/run_p34_fact_table_projection_and_goldcase_alignment.py`
  - no paid LLM
  - no true full-chain
  - generated preview/alignment artifacts

## 下一步口径

在用户认可本轮 deterministic preview 之前，不继续 true full-chain eval、paid model comparison 或 case expansion。

如果用户认可：

1. 先决定是否接受当前 fact-table surface 作为 P34 scoped writer 的下一版输入格式。
2. 再决定下一步是做 scoped paid writer rerun，还是优先深挖 parser/source：
   - DELL AI server margin bridge；
   - market price-in exact positioning；
   - semicap bookings/backlog/customer allocation；
   - source pages 的 numeric/table extraction。
