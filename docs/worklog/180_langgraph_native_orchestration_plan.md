# LangGraph 原生编排迁移计划

日期：2026-05-28  
分支：`codex/api-model-call-architecture`  
阶段：架构规划，尚未进入大规模改造

## 背景

最近 full78 覆盖版和 route-based retrieval 的测试暴露出一个更底层的问题：当前链路虽然已经有 `sec_agent_graph_runner.py` 和 `SecAgentState`，但主业务链路仍主要由 `scripts/cloud/sec_agent_interactive.py` 顺序驱动。LangGraph 目前更多承担外层包装、状态读取、artifact resume 和 smoke 入口，而不是业务编排核心。

当前实际形态：

- `scripts/cloud/sec_agent_interactive.py` 负责按固定顺序执行 planner、retrieval、market 注入、ledger、coverage、judgment plan、synthesis、verify、gates、render。
- `scripts/cloud/sec_agent_graph_runner.py` 使用 `StateGraph`，但核心节点仍是 `run_interactive_pipeline`，它内部调用既有 imperative pipeline。
- `src/sec_agent/graph_nodes.py` 定义了节点顺序、依赖和 artifact readiness，但这些节点还不是 LangGraph 原生可调度的业务节点。
- `src/sec_agent/tool_controller.py` / `src/sec_agent/tool_harness.py` 已经支持高层工具调用，但 tool loop 和 graph orchestration 没有深度融合；工具内部仍可能触发整个 DAG 或 artifact resume。
- resume 主要依赖 `sec_agent_state.json`、artifact path 和 digest，而不是 LangGraph 原生 checkpoint。

full78 阶段的 planner / scope 问题说明：如果脚本层提前把业务范围收窄，后续模型 planner、检索和 coverage 再努力也只能在错误范围内工作。下一阶段应把业务语义判断交给受约束的模型规划和图状态流转，把规则代码收回到 schema 校验、边界约束、证据覆盖和后置 gates。

## 目标

这次迁移的目标不是“换一个框架外壳”，而是让 LangGraph 成为主链路的业务编排层：

- 每个主要业务阶段成为独立 LangGraph node，输入输出都进入统一 state。
- planner 由 API 大模型在受约束 schema 下生成研究任务、证据需求、范围模式和 source tier，而不是由脚本先验判断业务重点。
- 确定性规则用于校验、编译、边界保护、证据覆盖和后置校验，不再用来替代模型做业务判断。
- 支持条件分支：证据充足则生成答案，证据不足且数据源存在则二次检索，问题范围不清或数据源不存在则请求澄清或输出带边界的答案。
- 支持 graph-level checkpoint / resume / interrupt / streaming / tracing，而不是只靠 artifact 扫描恢复。
- 将 tool calling / function calling 纳入 graph 循环，由 LangGraph 管理 `LLM -> tool -> observation -> LLM`，而不是在 graph 外层单独循环。

## 非目标

本阶段不做一次性重写，也不为了本机资源限制做特化逻辑：

- 不替换 BM25、ObjectBM25、BGE、DuckDB ledger store、market snapshot 等既有能力。
- 不放开模型任意访问底层索引；模型只能提出证据需求和受限工具调用，物理检索仍由编译器和工具执行。
- 不用 heuristic fallback 掩盖 planner 或 evidence requirement 失败；失败应进入 schema repair、retry、fail closed 或用户澄清。
- 不在文档或代码中写入任何 API key、密码、私有供应商令牌。
- 在迁移完成前保留现有 CLI / workbench / smoke 入口，确保可以回退到 legacy runner。

## 目标链路

目标状态下，业务 state 在 LangGraph 内流动，节点之间通过显式字段和 artifact refs 传递，不再靠一个脚本按顺序调用全部阶段。

```text
User turn
  -> load_session_state
  -> plan_query_with_llm
  -> validate_query_contract
  -> compile_evidence_requirements
  -> compile_retrieval_plan
  -> execute_retrieval_routes
  -> build_or_attach_market_snapshot
  -> build_runtime_ledger
  -> assess_evidence_coverage
  -> assess_evidence_sufficiency
      -> if sufficient: build_judgment_plan
      -> if insufficient and source exists: second_pass_retrieval
      -> if ambiguous or source missing: clarify_or_bounded_answer
  -> synthesize_answer
  -> verify_claims
  -> run_deterministic_gates
      -> if repairable: repair_answer
      -> if not repairable: bounded_answer
  -> render_answer
  -> persist_session_state
```

二次检索最多按受控预算循环，触发原因和检索结果写入后台 trace。最终答案中可以用自然语言说明“系统补充检查了某类证据后形成判断”，但不单独堆一个割裂的“二次检索证据区”，也不展示内部逐步推理链。

## Graph State Contract v1

LangGraph state 应覆盖以下字段。大对象仍可写入 artifact 文件，state 内保存摘要、digest 和引用。

| 字段 | 作用 |
|---|---|
| `session_identity` | tenant、user、session、thread、turn id |
| `user_query` | 当前用户问题、上一轮 follow-up 解析结果 |
| `source_inventory` | 当前可用公司、行业、年份、披露类型、source tier、market snapshot digest |
| `query_contract` | 公司范围、年份范围、披露类型、source policy、分析意图 |
| `evidence_requirement_plan` | 模型列出的证据需求、范围粒度、所需 source tier、指标族、文本解释需求 |
| `retrieval_plan` | 编译后的物理检索 route、候选预算、重排预算、coverage 要求 |
| `context_rows` | 检索到的文本证据和结构化对象，包含 route attribution |
| `market_snapshot_rows` | 市场快照、估值、事件窗口、`as_of_date` |
| `runtime_ledger_rows` | 可比财务事实，保留公司、财年、披露类型、期间口径、单位、来源对象 |
| `coverage_matrix` | 每个分析任务的证据覆盖、缺口、边界和 source tier 覆盖 |
| `evidence_sufficiency_report` | 是否足以回答、缺什么、是否允许二次检索、是否需要澄清 |
| `second_pass_requests` | 二次检索请求、预算、触发原因、执行结果 |
| `judgment_plan` | 生成答案前的可验证分析框架 |
| `memo_answer` | 大模型综合生成的研究备忘录草稿 |
| `claim_verification` | claim 支撑、降级、拒绝、证据引用 |
| `deterministic_gates` | source boundary、period role、market as-of-date、numeric support、forbidden claims |
| `rendered_answer` | 面向用户的最终答案 |
| `telemetry` | 每个 node 的耗时、token、候选数、BGE 数量、错误、artifact ref |

## 职责边界

| 层 | 职责 | 不该做的事 |
|---|---|---|
| LLM planner | 识别用户问题中的研究任务、公司范围、行业范围、年份范围、source tier、证据需求和分析意图 | 不直接决定物理索引路径，不绕过 schema，不凭记忆补事实 |
| Plan validator | 校验 planner 输出是否符合 schema、source inventory 和用户显式约束 | 不把 `ALL` 静默缩成少数行业或少数公司 |
| Retrieval compiler | 把 evidence requirement 编译为可执行 route，合并相同物理 scope，设置预算 | 不注入业务先验，不替代模型判断“哪些行业重要” |
| Retrieval tools | 执行 ledger-first、filing text、8-K commentary、market snapshot 等 route | 不跨 source policy 取证，不让 BGE 负责找数值事实 |
| Coverage / sufficiency | 判断每个分析任务是否有足够证据，决定是否二次检索或澄清 | 不用宽松 fallback 把缺口伪装成完整 |
| Synthesis | 在证据和 judgment plan 约束下写投研备忘录 | 不把市场快照写成 SEC 财务事实，不把管理层口径写成审计事实 |
| Gates | 校验来源边界、数值引用、期间口径、market snapshot 日期、claim support | 不做业务观点生成 |
| Renderer | 清晰呈现结论、证据边界、日期和 source tier | 不暴露内部 trace 的冗余细节 |

## 分阶段执行计划

### Phase 0：文档和现状对齐

目标：先固定迁移目标和执行边界，避免一边改一边扩大范围。

交付物：

- 本文档。
- `docs/worklog/README.md` 索引更新。
- 当前架构诊断：graph wrapper、artifact resume、tool harness 和 imperative pipeline 的边界。

验收：

- 文档说明清楚当前不是 LangGraph 原生业务编排。
- 后续代码变更能按阶段拆分，而不是直接重写整条链路。

### Phase 1：行为等价的 LangGraph 节点拆分

目标：先不改变业务结果，把当前主链路拆成真实 LangGraph nodes。

计划：

1. 新建或扩展 graph orchestrator，使用 `StateGraph(SecAgentGraphState)`。
2. 把当前阶段包装为独立 node：`plan_query`、`retrieve_context`、`attach_market_snapshot`、`build_ledger`、`build_coverage`、`build_judgment_plan`、`synthesize`、`verify`、`gates`、`render`。
3. 每个 node 读取和写入 state，不直接依赖全局脚本变量。
4. 每个 node 输出 artifact ref、stage timing、错误状态和关键统计。
5. 保留 legacy runner，新增 feature flag：`SEC_AGENT_ORCHESTRATOR=legacy|langgraph_native`。

验收：

- 现有单轮 full-source smoke 在 legacy 和 graph_native 下产物一致或只存在允许的 telemetry 差异。
- `trace_logs.jsonl` 能看到每个业务 node 的开始、结束、耗时和输出 artifact。
- 任一 node 失败时，state 中能定位失败阶段，而不是只返回脚本退出码。

### Phase 2：Planner / Scope 进入图状态

目标：修复 `ALL` 和 broad scope 被脚本提前缩窄的问题，让模型 planner 负责业务范围和证据需求。

计划：

1. planner 输出 `query_contract` 和 `evidence_requirement_plan`。
2. 增加 `scope_mode`：
   - `full_universe`：用户要求覆盖全部可用公司。
   - `sector_representative`：用户要求跨行业横向比较，允许模型选代表公司，但必须说明覆盖边界。
   - `focused_peer`：用户明确指定公司或 peer group。
3. `ALL` 只解析为 source inventory 的全量 universe，不在脚本层缩成 AI / 半导体 / 云公司。
4. validator 只校验用户显式约束、inventory 可达性和 schema，不做业务替换。
5. planner JSON 失败时走同模型 repair / retry；测试模式可以 fail closed，不启用 heuristic 业务兜底。

验收：

- full78 broad query 使用 `ALL` 时，`search_scope_count=78`。
- 模型可以在 `sector_representative` 下选择代表公司，但 state 要保留 `universe_count=78` 和 `representative_tickers` 的区别。
- heuristic planner 只作为 diagnostic 或离线对照，不作为主链路 silent fallback。

### Phase 3：EvidenceRequirementPlan 驱动检索

目标：让模型参与召回范围定义，但物理检索仍由编译器和工具受控执行。

计划：

1. `evidence_requirement_plan` 描述业务证据需求，例如“银行盈利质量”“医疗费用率”“AI capex 与 8-K 管理层解释”“市场估值反应”。
2. compiler 把需求转成物理 route：
   - `ledger_first`
   - `filing_text`
   - `8k_commentary`
   - `market_snapshot`
   - `risk_text`
3. 相同 ticker / year / source tier / filing type / section / metric family / query scope 合并成一个 physical search op。
4. ledger-first 优先查 DuckDB lightweight ledger store，不进入 BGE。
5. BGE 只对文本证据做 route-local rerank。
6. coverage reservation 保证行业、source tier、metric family、period role 不被单一高分公司挤掉。

验收：

- full78 宽问题不再产生全局扁平 5000+ 候选交给 BGE。
- `candidate_sent_to_bge` 与文本证据预算一致，ledger rows 不进入 BGE。
- context rows 保留 `selection_route_ids`，同一证据服务多条 route 时不复制文本。
- broad query 的 sector/source/period coverage 不因候选裁剪下降。

### Phase 4：证据充足性判断和二次检索

目标：模型发现证据不足时，不是只建议用户补查，而是在 source policy 允许且数据存在时自动触发二次检索。

计划：

1. 增加 `assess_evidence_sufficiency` node。
2. 输入包括 `query_contract`、`evidence_requirement_plan`、`coverage_matrix`、`ledger_rows`、`context_rows`、`source_inventory`。
3. 输出：
   - `sufficiency_level`: `sufficient | partial | insufficient`
   - `missing_requirements`
   - `source_available`
   - `second_pass_retrieval_requests`
   - `needs_user_clarification`
   - `bounded_answer_allowed`
4. 如果证据不足但 source inventory 显示 10-Q / 8-K / market snapshot 存在，则 graph 自动进入 `second_pass_retrieval`。
5. 二次检索后重新构建 coverage 和 sufficiency，最多执行受控轮数。
6. 若仍不足，最终答案仍输出当前证据能支持的观点，同时说明边界和还需要补充的数据范围。

验收：

- 当模型识别“应补查最新 10-Q / 8-K”且数据源存在时，系统实际二次检索，而不是只在答案里列建议。
- 二次检索触发原因写入后台 trace；面向用户的答案只融合说明，不新增割裂的证据列表区域。
- market snapshot 缺口不通过 SEC 检索补齐，仍由 market data 产品解决。

### Phase 5：Tool Calling / Function Calling 融入 LangGraph

目标：把当前 graph 外的 controller/harness loop 迁到 graph 内，让模型工具调用和条件边在同一状态机中运行。

计划：

1. 定义 graph-managed high-level tools：
   - `start_research`
   - `revise_scope`
   - `inspect_coverage`
   - `explain_evidence`
   - `resume_analysis`
   - `reformat_answer`
2. LLM node 只输出受控 tool call 或最终 response intent。
3. Tool node 执行工具并把 observation 写回 graph state。
4. 条件边决定继续工具循环、进入 synthesis、请求澄清或结束。
5. 旧 `tool_controller.py` / `tool_harness.py` 保留为兼容入口，逐步改为调用 graph runtime。

验收：

- 多轮 session 中，模型可以在图内选择 revise / inspect / resume，而不是外层脚本替它决定。
- 工具调用失败时 state 保存失败工具、参数、错误和可恢复节点。
- 不允许模型调用未注册低层文件或索引工具。

### Phase 6：原生 checkpoint / resume

目标：从 artifact resume 过渡到 graph checkpoint resume。

计划：

1. 先接 SQLite checkpointer，后续再评估 Postgres / Redis。
2. 每个 node 完成后保存 graph checkpoint。
3. 大 payload 仍写 artifact 文件，checkpoint 保存 path、digest、schema version 和摘要。
4. interrupt 后从最近成功 checkpoint 继续，而不是重新扫描所有 artifact 决定阶段。
5. 保留 artifact readiness 作为审计和兼容层。

验收：

- 可以从 retrieval 后、ledger 后、synthesis 后、gate 失败后恢复。
- 恢复后不重复执行已完成且 digest 未变化的重型阶段。
- 多 session 并发写状态不冲突。

### Phase 7：Workbench / API 集成

目标：让前端、CLI、API 都调用同一 graph runtime。

计划：

1. 后端接口暴露 graph run id、session id、thread id、node status、artifact refs。
2. 前端流式展示 node 进度、coverage、sufficiency、最终答案。
3. Profile / 数据源配置进入统一 source inventory，不让前端硬编码私有路径。
4. Workbench 的 smoke、单轮、多轮、resume 都走同一 graph API。

验收：

- 本地 workbench 可以启动 session、输入 API key、选择 profile、运行单轮、多轮和 resume。
- 用户界面能看到阶段进度和失败阶段。
- 同一 run 可用 CLI readiness 脚本复查。

## 验收用例

迁移过程中至少保留以下用例：

1. **full78 跨行业横向比较**  
   问题覆盖 AI、银行、医疗、工业、消费、能源、公用事业、地产等行业，验证 planner 不把 `ALL` 缩成少数科技公司。

2. **NVDA vs AMD 聚焦比较**  
   验证 focused peer scope、10-K / latest 10-Q / 8-K / market snapshot 的证据注入和 period role。

3. **证据不足但数据源存在**  
   模型识别需要最新 10-Q 或 8-K 后，系统自动二次检索并继续生成答案。

4. **证据不足且数据源不存在**  
   系统输出当前证据能支持的观点，并说明不能强推的结论和需要补充的数据。

5. **多轮 follow-up 缩窄范围**  
   第一轮 broad memo 后，用户追问“只展开 NVDA 和 AMD 差异”，系统复用上一轮 state、evidence pack 和 active answer。

6. **resume / interrupt**  
   在 retrieval、ledger、synthesis、gate 任一阶段中断，验证 graph checkpoint 能恢复。

7. **工具调用路径**  
   用户要求查看 coverage、解释证据、改 scope、重排答案格式，模型在 graph 内选择相应工具。

关键指标：

- `search_scope_count`
- `representative_ticker_count`
- `route_count`
- `sector_coverage`
- `source_tier_coverage`
- `candidate_pre_filter`
- `candidate_sent_to_bge`
- `ledger_row_count`
- `context_row_count`
- `second_pass_count`
- `sufficiency_level`
- `planner_ms / retrieval_ms / rerank_ms / ledger_ms / coverage_ms / synthesis_ms / gates_ms / render_ms`

## 风险与回滚

- 风险：拆节点时引入行为差异。  
  回滚：保留 `SEC_AGENT_ORCHESTRATOR=legacy`，直到 graph_native 通过 parity smoke。

- 风险：planner 输出自由度提高后范围变宽，导致检索成本上升。  
  控制：schema、source inventory、budget compiler、route merge 和 telemetry，不用业务 heuristic 静默缩窄。

- 风险：二次检索循环过深。  
  控制：固定最大轮数、候选预算和 source policy，超过后输出 bounded answer。

- 风险：checkpoint 和 artifact 双状态不一致。  
  控制：artifact digest、schema version、state fingerprint，并在 readiness 中校验。

## 当前决策

Decision label：`proceed`

下一步不直接重写整条链路。先执行 Phase 1 + Phase 2 的最小闭环：

1. 新增 LangGraph native orchestrator skeleton，先把现有阶段行为等价地拆成真实 node。
2. 修复 scope 进入 graph state：`ALL` 表示 inventory universe，代表公司选择只能作为 planner 输出的 `representative_tickers`。
3. 增加 full78 planner/scope parity tests，对比 heuristic planner、模型 planner 和显式 ticker scope。
4. 通过 parity smoke 后，再进入 EvidenceRequirementPlan 驱动的 graph retrieval 和二次检索条件边。

本轮只落文档和执行计划，未运行代码改造或全链路测试。

## 2026-05-28 Phase 1/2 最小实现记录

本轮开始执行 Phase 1 + Phase 2 的最小闭环，范围控制为“可验证的 graph-native skeleton + scope contract 修复”，没有搬迁 heavy retrieval / ledger / synthesis 主逻辑。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - 新增 LangGraph-native orchestration skeleton。
  - 固定 15 个业务节点：
    - `load_session_state`
    - `plan_query`
    - `validate_query_contract`
    - `compile_retrieval_plan`
    - `execute_retrieval_routes`
    - `attach_market_snapshot`
    - `build_runtime_ledger`
    - `assess_evidence_coverage`
    - `assess_evidence_sufficiency`
    - `build_judgment_plan`
    - `synthesize_answer`
    - `verify_claims`
    - `run_deterministic_gates`
    - `render_answer`
    - `persist_session_state`
  - 该 skeleton 当前是行为迁移入口，不调用真实 LLM / BGE / ledger；它证明 state 可以按业务节点在 LangGraph 内流动，并输出 `langgraph_native_summary.json`。
  - 新增 `scope_mode` 推断和 `annotate_scope_contract()`：
    - `full_universe`
    - `sector_representative`
    - `focused_peer`

- `src/sec_agent/query_contract.py`
  - Query Contract validator 现在会把 `scope_mode` 写入顶层和 `scope`。
  - `scope` 增加：
    - `universe_count`
    - `focus_count`
    - `representative_tickers`（仅 `sector_representative`）
  - 这使后续链路能区分“搜索范围是 full78”与“模型选择了代表公司写答案”。

- `scripts/cloud/sec_agent_interactive.py`
  - 修复 `_resolve_tickers("ALL", broad AI prompt, available)` 的旧行为。
  - `ALL/full/full30/*` 现在始终解析为当前 manifest / source inventory 的完整 universe。
  - AI 相关代表公司只能由 planner 通过 `focus_tickers` / `scope_mode=sector_representative` 表达，不能在脚本入口提前收窄 `search_scope_tickers`。

- `scripts/cloud/sec_agent_graph_runner.py`
  - 新增 `--native-state-smoke-dir`。
  - 该入口运行 LangGraph-native skeleton，不调用真实检索和模型，用于验证 graph nodes、state、summary artifact 是否可用。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 覆盖 `ALL` broad AI prompt 不再缩窄 universe。
  - 覆盖 Query Contract 的 `sector_representative` scope metadata。
  - 覆盖 LangGraph-native skeleton 可以执行完整节点序列并写 summary artifact。

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py src\sec_agent\query_contract.py scripts\cloud\sec_agent_interactive.py scripts\cloud\sec_agent_graph_runner.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `3 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py tests\test_sec_agent_10q_source_contract.py::test_interactive_mixed_policy_keeps_10q_when_planner_returns_10k_only tests\test_sec_agent_10q_source_contract.py::test_interactive_period_compare_is_not_peer_case_for_broad_search_scope -q`
  - `17 passed`
- `python scripts\cloud\sec_agent_graph_runner.py --native-state-smoke-dir .tmp_langgraph_native_smoke --prompt "native graph smoke" --no-checkpointer`
  - `status=completed`
  - `node_count=15`

### 当前边界

- native graph 目前是 skeleton，不替代主链路；真实 full-source run 仍走 legacy `sec_agent_interactive.py`。
- `execute_retrieval_routes`、`build_runtime_ledger`、`synthesize_answer` 等节点还没有接入真实工具。
- scope 修复只解决入口层 `ALL` 被脚本收窄的问题；planner 仍需继续在 Phase 2 中输出更明确的 `scope_mode` 和 EvidenceRequirementPlan。
- 暂未引入 graph-native checkpoint；当前 skeleton 使用可选 `InMemorySaver`，正式 resume 迁移留到 Phase 6。

### 下一步

继续 Phase 2：

1. 在 planner prompt / normalizer 中显式加入 `scope_mode`。
2. planner 输出中区分：
   - `search_scope_tickers`
   - `focus_tickers`
   - `representative_tickers`
   - `scope_mode`
3. 增加 full78 planner/scope parity tests：
   - `ALL` + broad cross-sector prompt。
   - 显式 full78 ticker list。
   - 聚焦 `NVDA,AMD`。
4. native graph 中把 `plan_query` 从 smoke stub 替换为调用现有 planner 函数的行为等价 node。

## 2026-05-28 Phase 2 Planner Scope Contract 实施记录

本轮继续推进 Phase 2，把 planner scope 合同显式化，核心目标是让模型可以参与“代表公司/证据需求”规划，但不能把系统检索范围静默缩窄。

### 已实现

- `scripts/cloud/sec_agent_interactive.py`
  - planner system prompt 增加 `scope_mode` 合同：
    - `full_universe`
    - `sector_representative`
    - `focused_peer`
  - planner JSON schema 增加：
    - `scope_mode`
    - `search_scope_tickers`
    - `focus_tickers`
    - `representative_tickers`
  - normalizer 明确忽略模型对 `search_scope_tickers` 的缩窄，系统仍使用 inventory 解析出的完整 `tickers` 作为 search scope。
  - 如果模型输出 `scope_mode=full_universe` 但 `focus_tickers` 只是 subset，normalizer 会改为 `sector_representative`，避免“全范围问题被代表样本伪装成全覆盖”。
  - planner seed、planner summary、plan preview 输出都带上 `scope_mode` 和 search/focus 计数。

- `src/sec_agent/query_contract.py`
  - Query Contract validator 同步处理 `scope_mode=full_universe` 但 focus subset 的矛盾，规范为 `sector_representative`。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加模型 planner scope 合同测试：即使 planned JSON 只给出 `["NVDA", "AMD"]` 的 `search_scope_tickers`，系统验证后的 `search_scope_tickers` 仍保留 `["NVDA", "AMD", "JPM", "XOM"]`。
  - 增加 prompt contract 测试：确认 planner prompt 暴露 `scope_mode`、`search_scope_tickers`、`representative_tickers` 和 `evidence_requirements`。

### 验证

- `python -m py_compile scripts\cloud\sec_agent_interactive.py src\sec_agent\query_contract.py src\sec_agent\langgraph_orchestrator.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `5 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py tests\test_sec_agent_10q_source_contract.py::test_interactive_mixed_policy_keeps_10q_when_planner_returns_10k_only tests\test_sec_agent_10q_source_contract.py::test_interactive_period_compare_is_not_peer_case_for_broad_search_scope -q`
  - `17 passed`
- `pytest tests\test_sec_agent_8k_earnings_source.py::test_planner_prompt_uses_compact_json_contract tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_limits_tasks_and_field_lengths tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract tests\test_sec_agent_8k_earnings_source.py::test_context_session_forwards_source_gap_path_to_graph_args -q`
  - `4 passed`
- native graph smoke:
  - `python scripts\cloud\sec_agent_graph_runner.py --native-state-smoke-dir .tmp_langgraph_native_smoke --prompt "native graph scope smoke" --no-checkpointer`
  - `status=completed`
  - `node_count=15`
- full78 plan-only scope check:
  - `--query-planner heuristic --tickers ALL --years 2026 --manifest-path data\processed_private\manifests\sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl`
  - 输出：`scope_mode=sector_representative scope=78 companies focus=NVDA,AMD,AVGO,AMAT,MU,INTC,QCOM,MSFT,GOOGL,AMZN,META,ADBE,SNOW`
  - retrieval plan：`routes_by_type=8k_commentary=4,filing_text=4,ledger_first=4,market_snapshot=4,risk_text=1`

### 当前边界

- 这一步仍未把真实 planner node 接入 native graph；native graph 的 `plan_query` 仍是 skeleton。
- heuristic planner 仍会在 AI 宽问题中选择 AI 代表公司作为 `focus_tickers`，但 `search_scope_tickers` 已保留 full78，后续 retrieval/coverage 可以基于完整 universe 做审计。
- 真正的模型 planner full78 对比还没跑；下一步需要用 DeepSeek planner 做 explicit full78 / ALL / focused peer 三组 parity。

### 下一步

1. 将现有 planner build/validate 逻辑封成可注入函数，供 native graph `plan_query` node 调用。
2. 新增 planner parity eval：
   - `ALL` broad cross-sector prompt。
   - explicit full78 ticker list。
   - focused `NVDA,AMD` prompt。
3. 对比 heuristic planner 与 LLM planner 的：
   - `search_scope_count`
   - `scope_mode`
   - `focus_count`
   - `evidence_requirement_count`
   - `retrieval route_counts`
   - 是否错误缩窄 source scope。

## 2026-05-28 Phase 2 Native Planner Adapter 实施记录

本轮把现有 planner 构建逻辑接入 LangGraph-native skeleton 的 `plan_query` 节点，目标是验证“真实 planner 输出进入 graph state”这一步，而不是继续让 native graph 只跑固定 stub。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - `build_native_orchestration_graph()` 支持注入 `plan_query` callable。
  - `plan_query` 节点会把注入 planner 返回的 `query_contract`、`planner_trace`、`project_inventory`、`selected_tickers`、`selected_years` 写入 graph state。
  - 后续 `validate_query_contract`、`compile_retrieval_plan`、`persist_session_state` 节点使用同一份 graph state 继续流转。
  - `node_trace` 增加节点级 metadata，便于 smoke 阶段确认每个节点消费和产出的核心摘要。

- `scripts/cloud/sec_agent_interactive.py`
  - 新增 `build_query_plan_for_graph(args, prompt)` adapter。
  - 该 adapter 复用现有 manifest 解析、source inventory、planner prompt、contract normalize 和 validation 逻辑，不复制一套 planner。
  - 返回给 graph 的内容包含：
    - `query_contract`
    - `planner_trace`
    - `project_inventory`
    - `selected_tickers`
    - `selected_years`

- `scripts/cloud/sec_agent_graph_runner.py`
  - 新增 `--native-plan-smoke-dir`。
  - 该入口把命令行参数解析为 legacy interactive args，再通过 injected planner callable 交给 native graph。
  - 修复 graph runner 转发参数时把 `--` 分隔符传入底层 parser 的问题。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加 native graph injected planner 测试。
  - 增加 interactive planner adapter 测试，验证 `ALL` 在 adapter 层仍保留完整 manifest scope，不被 broad AI prompt 收窄。

### 验证

- `python -m py_compile scripts\cloud\sec_agent_graph_runner.py src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `7 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py::test_planner_evidence_requirements_drive_physical_routes tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract -q`
  - `2 passed`
- native planner smoke：
  - `python scripts\cloud\sec_agent_graph_runner.py --native-plan-smoke-dir .tmp_langgraph_native_plan_smoke --prompt "结合当前覆盖公司，比较这些公司在 AI 相关业务、管理层解释和市场反应上的表现" --no-checkpointer -- --query-planner heuristic --tickers ALL --years 2026 --manifest-path data\processed_private\manifests\sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl`
  - `status=completed`
  - `node_count=15`
  - `scope_mode=sector_representative`
  - `search_scope_count=78`
  - `focus_count=13`
  - `retrieval_routes=8k_commentary=4, filing_text=4, ledger_first=4, market_snapshot=4, risk_text=1`

### 当前边界

- native graph 现在已经可以承载真实 planner / query contract / retrieval plan 编译，但还没有执行真实 retrieval、ledger、coverage、synthesis、gates 和 renderer。
- planner adapter 仍复用 `sec_agent_interactive.py` 内部函数；下一阶段需要把 planner、retrieval、ledger 等能力逐步拆成可独立调用的 service/tool 模块，减少 graph node 对 legacy script 的依赖。
- 本轮 smoke 使用 heuristic planner 验证 graph state 和 scope contract。模型 planner 对比仍需单独跑 `ALL`、explicit full78、focused peer 三组 parity。

### 下一步

1. 在 native graph 中接入 `execute_retrieval_routes` 的真实执行路径，先只跑 plan-driven retrieval，不进入 synthesis。
2. 把 EvidenceRequirementPlan 的 route 合并、候选预算和 telemetry 写入 graph state。
3. 增加 evidence sufficiency 条件边：
   - 证据不足且仍有可查 source scope 时，进入一次二次检索。
   - 二次检索后仍不足时，输出 bounded answer，并在正文自然说明证据边界。
4. 跑 heuristic planner 与 API 模型 planner 的 scope parity，对比 retrieval route 和 candidate stats。

## 2026-05-28 Phase 3 Retrieval Node Adapter 实施记录

本轮继续向 Phase 3 推进，但仍控制迁移范围：只把真实 context retrieval 的调用口接入 native graph，不迁移 synthesis，也不在本地触发重型 BGE 全检索。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - `build_native_orchestration_graph()` 增加 `retrieve_context` callable 注入点。
  - `execute_retrieval_routes` 节点现在支持两种模式：
    - 未注入时保留 `state_stub`，用于纯状态 smoke。
    - 注入时调用外部 retrieval adapter，把 `context_rows`、`retrieval_trace`、`context_runtime` 和 `artifact_refs` 写回 graph state。
  - `node_trace` 记录 `context_row_count` 和 `context_runner`，为后续 stage-level telemetry 铺路。

- `scripts/cloud/sec_agent_interactive.py`
  - 新增 `retrieve_context_for_graph(args, graph_state)` adapter。
  - 该 adapter 复用现有 `_build_case()`、`build_retrieval_plan()`、`_run_context()` 和 trace 读取逻辑。
  - 输出 graph 可消费的结构：
    - `context_rows`
    - `retrieval_trace`
    - `context_runtime`
    - `artifact_refs.case`
    - `artifact_refs.retrieval_plan`
    - `artifact_refs.retrieved_context`

- `scripts/cloud/sec_agent_graph_runner.py`
  - 新增 `--native-retrieval-smoke-dir`。
  - 该入口把 planner adapter 和 retrieval adapter 同时注入 native graph，完成到 `execute_retrieval_routes` 的真实阶段接线；后续节点仍保持非 LLM stub。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加 injected retrieval node 测试，确认 retrieval node 能消费已编译的 `retrieval_plan` 并把 context 写回 state。
  - 增加 interactive retrieval adapter 测试，通过 monkeypatch `_run_context()` 验证 case、retrieval_plan、trace artifact 的写入与读取，不触发真实 BGE。

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py scripts\cloud\sec_agent_graph_runner.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `9 passed`
- native planner smoke：
  - `python scripts\cloud\sec_agent_graph_runner.py --native-plan-smoke-dir .tmp_langgraph_native_plan_smoke --prompt "结合当前覆盖公司，比较这些公司在 AI 相关业务、管理层解释和市场反应上的表现" --no-checkpointer -- --query-planner heuristic --tickers ALL --years 2026 --manifest-path data\processed_private\manifests\sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl`
  - `status=completed`
  - `node_count=15`
  - `search_scope_count=78`
  - `retrieval_routes=8k_commentary=4, filing_text=4, ledger_first=4, market_snapshot=4, risk_text=1`

### 当前边界

- `--native-retrieval-smoke-dir` 是真实 retrieval 接线入口，但本轮未在本地跑 full78 + BGE 检索；本地验证用 fake retrieval，避免把架构迁移验证和本机资源瓶颈混在一起。
- native graph 仍没有接入 market attach、runtime ledger、coverage、judgment plan、synthesis、claim verify、gates 和 renderer 的真实执行。
- `retrieve_context_for_graph()` 仍调用 legacy `_run_context()`；这是行为等价迁移的中间层，后续需要继续拆成 graph-native retrieval service。

### 下一步

1. 在云端或具备 CUDA/BGE 环境时跑 `--native-retrieval-smoke-dir` 的真实 retrieval smoke，记录 context rows、candidate stats、BGE 时间和 route coverage。
2. 把 `attach_market_snapshot` 和 `build_runtime_ledger` 两个节点接入真实 adapter。
3. 在 `assess_evidence_sufficiency` 后加入条件边和一次二次检索循环，但保持最终答案为连续 memo，不单独展示“补查列表”。
4. 对比 legacy imperative pipeline 与 native graph 到 retrieval/ledger 的 artifact parity。

## 2026-05-28 Phase 3 Market / Ledger Node Adapter 实施记录

本轮继续把 retrieval 之后的两个确定性阶段接入 native graph：市场快照注入和运行时精确值台账。范围仍限制在 adapter 接线与单测，不触发 LLM synthesis。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - `build_native_orchestration_graph()` 增加：
    - `attach_market_snapshot` callable 注入点。
    - `build_runtime_ledger` callable 注入点。
  - `attach_market_snapshot` 节点会把 `market_snapshot_rows`、更新后的 `context_rows`、`retrieval_trace` 和 artifact refs 写回 graph state。
  - `build_runtime_ledger` 节点会把 `runtime_ledger_rows` 和 ledger artifact ref 写回 graph state。
  - 两个节点的 `node_trace` 均记录 mode 和 row count。

- `scripts/cloud/sec_agent_interactive.py`
  - 新增 `attach_market_snapshot_for_graph(args, graph_state)`。
    - 复用 `_contract_requests_market_snapshot()`、`_load_market_context_rows()` 和 `_append_unique_context_rows()`。
    - 写出 `market_snapshot_context_rows.jsonl`，并在 trace 存在时同步更新 `trace_logs.jsonl`。
  - 新增 `build_runtime_ledger_for_graph(args, graph_state)`。
    - 复用 `_build_runtime_ledger()`。
    - 写出 `runtime_exact_value_ledger.json`。

- `scripts/cloud/sec_agent_graph_runner.py`
  - 新增 `--native-ledger-smoke-dir`。
  - 该入口将 planner、retrieval、market attach、runtime ledger 四个 adapter 一并注入 native graph；后续 coverage/synthesis/gates 仍保持 stub。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加 native graph market + ledger adapter state 传递测试。
  - 增加 interactive market + ledger adapter artifact 写入测试，通过 monkeypatch 避免真实检索和真实 ledger 依赖。

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py scripts\cloud\sec_agent_graph_runner.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `11 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py::test_planner_evidence_requirements_drive_physical_routes tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract -q`
  - `2 passed`
- `python scripts\cloud\sec_agent_graph_runner.py --help | Select-String -Pattern "native-(state|plan|retrieval|ledger)-smoke"`
  - 确认四个 native smoke 入口均暴露。
- native planner smoke 仍通过：
  - `status=completed`
  - `node_count=15`
  - `search_scope_count=78`
  - `retrieval_routes=8k_commentary=4, filing_text=4, ledger_first=4, market_snapshot=4, risk_text=1`

### 当前边界

- native graph 已经可以承载 planner、retrieval、market attach、runtime ledger 四类真实 adapter，但仍不是最终 LangGraph-native 主链路。
- 当前 adapter 仍调用 legacy script 内部函数；这符合行为等价迁移策略，但后续需要把 retrieval service、market evidence store、ledger store 拆成独立模块，减少对 `sec_agent_interactive.py` 的依赖。
- 尚未接入真实 coverage matrix、evidence sufficiency 条件边、二次检索循环、judgment plan、LLM synthesis、claim verification、deterministic gates 和 renderer。

### 下一步

1. 接入 `assess_evidence_coverage` 真实节点，复用现有 `build_coverage_matrix()`。
2. 将 `assess_evidence_sufficiency` 改成基于 coverage matrix 的结构化判断，并产出二次检索请求。
3. 用 LangGraph conditional edge 管理一次二次检索循环，而不是由脚本内部顺序调用。
4. 在云端跑 `--native-ledger-smoke-dir` 的真实检索 + ledger smoke，并与 legacy run 的 artifact 做 parity。

## 2026-05-28 Phase 3 Coverage Node Adapter 实施记录

本轮继续接入 evidence coverage matrix。这个节点是后续二次检索条件边的决策依据，因此优先于 LLM synthesis 迁移。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - `build_native_orchestration_graph()` 增加 `build_coverage_matrix` callable 注入点。
  - `assess_evidence_coverage` 节点支持：
    - `state_stub`：使用已有 state 或生成最小 coverage summary。
    - `injected`：调用 adapter，把 `coverage_matrix` 和 artifact refs 写回 graph state。
  - 节点 trace 会记录 coverage summary，便于后续 SLA / telemetry 归集。

- `scripts/cloud/sec_agent_interactive.py`
  - 新增 `build_coverage_matrix_for_graph(args, graph_state)`。
  - 复用现有 `build_coverage_matrix()`，输入为 graph state 中的 `query_contract`、`context_rows`、`runtime_ledger_rows`。
  - 写出 `runtime_evidence_coverage_matrix.json`。

- `scripts/cloud/sec_agent_graph_runner.py`
  - `--native-ledger-smoke-dir` 现在会一路注入 planner、retrieval、market attach、runtime ledger 和 coverage adapter。
  - 输出 summary 增加 `coverage` 字段。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - native graph market/ledger 测试扩展到 coverage。
  - interactive adapter 测试扩展到 coverage artifact 写入。

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py scripts\cloud\sec_agent_graph_runner.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `11 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py::test_planner_evidence_requirements_drive_physical_routes tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract -q`
  - `2 passed`
- native planner smoke 仍通过：
  - `status=completed`
  - `node_count=15`
  - `search_scope_count=78`
  - `retrieval_routes=8k_commentary=4, filing_text=4, ledger_first=4, market_snapshot=4, risk_text=1`

### 当前边界

- `assess_evidence_sufficiency` 仍是简单读取 coverage summary 的 stub，没有生成可执行的 second-pass retrieval request。
- 真实二次检索仍在 legacy `_stage_maybe_second_pass_retrieval()` 中；下一步要把这部分改成 LangGraph conditional edge。
- 还未接入 judgment plan、LLM synthesis、claim verification、deterministic gates 和 renderer 的真实 adapter。

### 下一步

1. 设计 `EvidenceSufficiencyReport` schema：
   - `sufficiency_level`
   - `missing_requirements`
   - `second_pass_requests`
   - `bounded_answer_allowed`
   - `user_clarification_required`
2. 将 `assess_evidence_sufficiency` 改成真实节点，不做业务兜底，只基于 coverage 和 query contract 判断。
3. 用 LangGraph conditional edge 实现最多一次二次检索：
   - `assess_evidence_sufficiency -> execute_second_pass_retrieval -> build_runtime_ledger -> assess_evidence_coverage`
   - 或 `assess_evidence_sufficiency -> build_judgment_plan`
4. 最终答案中自然说明二次检索触发原因和证据边界，后台日志保留具体 second-pass request 和命中结果。

## 2026-05-28 Phase 4 Evidence Sufficiency Report 实施记录

本轮先落 `EvidenceSufficiencyReport`，为后续 LangGraph conditional edge 做准备。当前只生成二次检索请求，不实际执行 second-pass loop。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - `assess_evidence_sufficiency` 从简单布尔判断升级为结构化报告。
  - 新报告字段：
    - `schema_version`
    - `sufficiency_level`
    - `coverage_complete`
    - `primary_task_support_complete`
    - `answer_status`
    - `missing_requirements`
    - `second_pass_retrieval_requests`
    - `bounded_answer_allowed`
    - `user_clarification_required`
  - 从 coverage matrix task 中提取缺口：
    - missing tickers
    - missing years
    - missing filing types
    - missing source tiers
    - missing metric families
    - missing market fields
  - 对可检索缺口生成最多 5 条 `second_pass_retrieval_requests`，供下一步 conditional edge 消费。
  - node trace 增加：
    - `sufficiency_level`
    - `missing_requirement_count`
    - `second_pass_request_count`

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加 partial coverage 场景测试。
  - 验证缺少 AMD / FY2026 / 10-Q / capex 证据时，sufficiency report 会产生对应 second-pass request。

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py scripts\cloud\sec_agent_graph_runner.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `12 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py::test_planner_evidence_requirements_drive_physical_routes tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract -q`
  - `2 passed`
- native planner smoke 仍通过：
  - `status=completed`
  - `node_count=15`
  - `search_scope_count=78`
  - `retrieval_routes=8k_commentary=4, filing_text=4, ledger_first=4, market_snapshot=4, risk_text=1`

### 当前边界

- 现在只是把二次检索请求结构化生成，还没有 LangGraph 条件边真正执行 second pass。
- report 只使用 coverage matrix 已有缺口字段，不额外引入业务 heuristic。
- 最终输出的“自然说明二次检索触发原因和结果”还要等 synthesis / renderer 迁移时接入。

### 下一步

1. 在 graph 中新增 `execute_second_pass_retrieval` 节点。
2. 增加 conditional edge：
   - 有 `second_pass_retrieval_requests` 且未超过轮数：进入二次检索。
   - 否则进入 `build_judgment_plan`。
3. 二次检索后重新运行 ledger 和 coverage，再生成新的 sufficiency report。
4. 记录 second-pass telemetry：请求数、命中 rows、增加 ledger rows、coverage 是否改善。

## 2026-05-28 Phase 4 Conditional Second-Pass Loop 实施记录

本轮把二次检索从 legacy 脚本顺序调用迁入 LangGraph conditional edge。现在 graph 会根据 `EvidenceSufficiencyReport` 决定是否进入一次 second-pass retrieval；二次检索后重新跑 ledger、coverage 和 sufficiency，再继续进入 judgment plan。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - 新增 optional node：`execute_second_pass_retrieval`。
  - `native_node_order()` 仍表示无二次检索的主路径；second-pass node 只在条件满足时进入。
  - 新增条件边：
    - `assess_evidence_sufficiency -> execute_second_pass_retrieval`
    - `assess_evidence_sufficiency -> build_judgment_plan`
  - `execute_second_pass_retrieval -> build_runtime_ledger -> assess_evidence_coverage -> assess_evidence_sufficiency` 形成最多一次循环。
  - 进入二次检索的条件：
    - 已配置 `execute_second_pass_retrieval` adapter。
    - `evidence_sufficiency_report.second_pass_retrieval_requests` 非空。
    - `second_pass_attempts < max_second_passes`，默认最多 1 次。
  - `execute_second_pass_retrieval` 节点把以下字段写回 graph state：
    - `context_rows`
    - `retrieval_trace`
    - `context_runtime`
    - `second_pass_attempts`
    - `second_pass_result`
    - `artifact_refs`

- `scripts/cloud/sec_agent_interactive.py`
  - 新增 `execute_second_pass_retrieval_for_graph(args, graph_state)`。
  - 该 adapter 从 `EvidenceSufficiencyReport.second_pass_retrieval_requests` 编译二次检索 requirements。
  - 复用 legacy 里的：
    - `_second_pass_query_contract()`
    - `build_retrieval_plan()`
    - `_run_context()`
    - `_append_unique_context_rows()`
    - `_merge_second_pass_trace()`
  - 写出：
    - `second_pass_retrieval_trace.json`
    - `second_pass_retrieval_<N>/case.jsonl`
    - `second_pass_retrieval_<N>/query_contract.json`
    - `second_pass_retrieval_<N>/retrieval_plan.json`
    - `second_pass_retrieval_<N>/trace/trace_logs.jsonl`
  - 主 trace 会合并二次检索 context rows，但最终答案展示仍留给 synthesis/renderer 迁移阶段处理。

- `scripts/cloud/sec_agent_graph_runner.py`
  - `--native-ledger-smoke-dir` 现在注入 second-pass adapter。
  - 输出 summary 增加 `second_pass` 字段。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加 conditional second-pass loop 测试：
    - 第一次 coverage 不足。
    - graph 进入 `execute_second_pass_retrieval`。
    - 二次检索后重新执行 ledger、coverage、sufficiency。
    - 最终 sufficiency 变为 `sufficient`。
  - 增加 interactive second-pass adapter 测试：
    - fake `_run_context()` 写入二次检索 trace。
    - adapter 合并 context rows，并写出 second-pass artifacts。

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py scripts\cloud\sec_agent_graph_runner.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `14 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py::test_planner_evidence_requirements_drive_physical_routes tests\test_sec_agent_retrieval_plan.py::test_second_pass_requirements_compile_searchable_coverage_gaps tests\test_sec_agent_retrieval_plan.py::test_second_pass_stage_merges_context_and_writes_trace tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract -q`
  - `4 passed`
- native planner smoke 仍通过：
  - `status=completed`
  - `node_count=15`
  - `scope_mode=sector_representative`
  - `search_scope_count=78`
  - `focus_count=13`
  - `retrieval_routes=8k_commentary=4, filing_text=4, ledger_first=4, market_snapshot=4, risk_text=1`

### 当前边界

- 真实 BGE / full78 的 `--native-ledger-smoke-dir` 尚未在本轮本地执行；本轮用单测 fake retrieval 验证 graph 条件边和 artifact 接线。
- second-pass request 目前来自 coverage matrix 缺口字段；更细的“模型自我反思式补查请求”还没接入。
- judgment plan、LLM synthesis、claim verification、deterministic gates 和 renderer 仍是 stub。

### 下一步

1. 在云端跑 `--native-ledger-smoke-dir` 的真实 retrieval + second-pass + ledger + coverage smoke。
2. 对比 native graph 到 coverage 的 artifact 与 legacy full-source run：
   - query contract
   - retrieval plan
   - trace/context rows
   - runtime ledger
   - coverage matrix
   - second-pass trace
3. 接入 `build_judgment_plan` 真实 adapter。
4. 迁移 synthesis/gates/renderer，并让最终 memo 自然说明二次检索触发和证据边界，不单独输出割裂的“补查列表”。

## 2026-05-28 Phase 5 Judgment Plan Adapter 实施记录

本轮把 `build_judgment_plan` 从 native graph 的占位节点接到现有 deterministic Judgment Plan 构建脚本。现在 native LangGraph 在完成 retrieval、market attach、runtime ledger、coverage、sufficiency 和可选 second-pass 后，会由 graph 节点直接生成 `runtime_judgment_plan.json`，而不是继续停留在 stub。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - `build_native_orchestration_graph()` 增加 `build_judgment_plan` adapter 参数。
  - `build_judgment_plan` node 支持注入真实 adapter，并把以下内容写回 graph state：
    - `judgment_plan`
    - `artifact_refs.judgment_plan`
  - node trace 增加 metadata：
    - `mode=injected`
    - `has_plan`
    - `driver_count`

- `scripts/cloud/sec_agent_interactive.py`
  - 新增 `build_judgment_plan_for_graph(args, graph_state)`。
  - adapter 将 graph state 物化成 legacy Judgment Plan 脚本需要的输入：
    - `case.jsonl`
    - `trace/trace_logs.jsonl`
    - `runtime_exact_value_ledger.json`
    - `runtime_evidence_coverage_matrix.json`（存在 coverage state 时）
  - 复用现有 deterministic plan 构建脚本：
    - `scripts/build_sec_benchmark_judgment_plan.py`
  - 保留现有交互链路后处理：
    - `_compact_plan_payload_for_interactive()`
    - `_augment_plan_payload_with_market_snapshot()`
  - ledger row 进入 plan 前会补齐 `case_id`，这是 legacy plan builder 的输入契约，不改变业务事实。

- `scripts/cloud/sec_agent_graph_runner.py`
  - `--native-ledger-smoke-dir` 注入 `build_judgment_plan_for_graph()`。
  - summary 增加 `judgment_plan.has_plan` 和 `judgment_plan.driver_count`。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加 native graph judgment plan adapter 注入测试。
  - 增加 interactive graph judgment plan adapter artifact 测试，验证：
    - case/trace/ledger/plan 文件写出；
    - ledger row 的 `case_id` 契约正确；
    - graph state 返回 selected `judgment_plan`。

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py scripts\cloud\sec_agent_graph_runner.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `16 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py::test_planner_evidence_requirements_drive_physical_routes tests\test_sec_agent_retrieval_plan.py::test_second_pass_requirements_compile_searchable_coverage_gaps tests\test_sec_agent_retrieval_plan.py::test_second_pass_stage_merges_context_and_writes_trace tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract -q`
  - `4 passed`
- native planner smoke 通过：
  - manifest：`data/processed_private/manifests/sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl`
  - `status=completed`
  - `node_count=15`
  - `scope_mode=sector_representative`
  - `search_scope_count=78`
  - `focus_count=5`
  - `retrieval_routes=8k_commentary=4, filing_text=4, ledger_first=4, market_snapshot=4, risk_text=1`

### 当前边界

- 本地未跑真实 `--native-ledger-smoke-dir`，因为它会触发 BGE/retrieval/ledger 全链路，当前阶段只验证 adapter 接线和 deterministic plan artifact 契约。
- `synthesize_answer`、`verify_claims`、`run_deterministic_gates` 和 `render_answer` 仍是 native graph stub。
- 模型自反式二次检索请求尚未接入；当前 second-pass request 仍来自 coverage/sufficiency 的结构化缺口。

### 下一步

1. 迁移 `synthesize_answer` adapter，让 native graph 从 `judgment_plan`、`context_rows`、`runtime_ledger_rows` 和 `coverage_matrix` 生成真实 memo。
2. 迁移 `verify_claims` 和 deterministic gates。
3. 迁移 renderer，并在最终答案中自然说明二次检索触发原因和证据边界。
4. 在云端或本地 CUDA 环境跑一次真实 `--native-ledger-smoke-dir`，验证 retrieval 到 judgment plan 的全 artifact 链。

## 2026-05-28 Phase 6 Synthesis Adapter 实施记录

本轮把 `synthesize_answer` 从 native graph 的占位节点改成可注入节点，并新增真实 synthesis adapter。默认 `--native-ledger-smoke-dir` 暂不注入 synthesis，避免确定性 smoke 变成必须依赖 API key 的模型调用；后续会单独增加 full native run 入口。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - `build_native_orchestration_graph()` 增加 `synthesize_answer` adapter 参数。
  - `synthesize_answer` node 支持注入真实 adapter，并把以下字段写回 graph state：
    - `memo_answer`
    - `claim_verification`
    - `rendered_answer`
    - `artifact_refs`
  - node trace 增加 metadata：
    - `mode=injected`
    - `answer_status`
    - `claim_status`

- `scripts/cloud/sec_agent_interactive.py`
  - 新增 `synthesize_answer_for_graph(args, graph_state)`。
  - adapter 从 graph state 读取：
    - `query_contract`
    - `context_rows`
    - `runtime_ledger_rows`
    - `coverage_matrix`
    - `judgment_plan`
  - 复用 legacy synthesis 关键逻辑：
    - `_select_synthesis_evidence_pack()`
    - `_ask_llm_server()`
    - `_normalize_or_fallback()`
    - `verify_answer_claims()`
    - `_write_run_outputs()`
  - 写出：
    - `runtime_evidence_pack.json`
    - `qwen/agent_outputs.jsonl`
    - `qwen/claim_verification.jsonl`
    - `qwen/scores.jsonl`
    - `qwen/trace_logs.jsonl`
    - `qwen/raw_model_outputs.jsonl`
    - `qwen/run_summary.json`
    - `qwen/input_output.md`
    - `qwen/rendered_answer.md`

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加 native graph synthesis adapter 注入测试。
  - 增加 interactive graph synthesis adapter artifact 测试，通过 monkeypatch 模型调用验证输出契约，不依赖真实 API key。

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py scripts\cloud\sec_agent_graph_runner.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `18 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py::test_planner_evidence_requirements_drive_physical_routes tests\test_sec_agent_retrieval_plan.py::test_second_pass_requirements_compile_searchable_coverage_gaps tests\test_sec_agent_retrieval_plan.py::test_second_pass_stage_merges_context_and_writes_trace tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract -q`
  - `4 passed`
- native planner smoke 仍通过：
  - manifest：`data/processed_private/manifests/sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl`
  - `status=completed`
  - `node_count=15`
  - `scope_mode=sector_representative`
  - `search_scope_count=78`
  - `focus_count=5`
  - `retrieval_routes=8k_commentary=4, filing_text=4, ledger_first=4, market_snapshot=4, risk_text=1`

### 当前边界

- `verify_claims` 作为独立 LangGraph node 仍未迁移成真实 adapter；当前真实 claim verification 仍在 synthesis adapter 内复用 legacy 行为。
- deterministic gates 和 renderer 仍是 native graph stub。
- 真实 API full native synthesis run 尚未执行；本轮只验证 adapter 接口和 artifact 契约。

### 下一步

1. 将 `verify_claims` 从 synthesis 内部副作用拆成 native graph 可注入 adapter，保证 graph state 中的 claim report 可独立 checkpoint。
2. 接入 deterministic gates adapter。
3. 接入 renderer adapter。
4. 增加一个明确需要 API key 的 full native run/smoke 入口，用于从 planner 到 renderer 的真实端到端测试。

## 2026-05-28 Phase 7 Gates And Renderer Adapter 实施记录

本轮继续迁移 synthesis 之后的确定性后处理节点：`run_deterministic_gates` 和 `render_answer`。这两个节点现在都支持 native graph adapter 注入，可以从 graph state 与已保存 artifact 中恢复输入并写回输出。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - `build_native_orchestration_graph()` 增加：
    - `run_deterministic_gates`
    - `render_answer`
  - `run_deterministic_gates` node 支持注入 adapter，写回：
    - `deterministic_gates`
    - `artifact_refs.deterministic_gates`
  - `render_answer` node 支持注入 adapter，写回：
    - `rendered_answer`
    - `artifact_refs.rendered_answer`
  - node trace 增加 adapter metadata，便于判断这些节点是否仍是 smoke stub。

- `scripts/cloud/sec_agent_interactive.py`
  - 新增 `run_deterministic_gates_for_graph(args, graph_state)`。
    - 从 graph state 物化 `case.jsonl`、`runtime_exact_value_ledger.json` 和必要的 `runtime_judgment_plan.json`。
    - 调用现有 `_run_post_gates()`。
    - 读取 `post_gates/sec_benchmark_post_gates_summary.json` 并写回 `deterministic_gates`。
  - 新增 `render_answer_for_graph(args, graph_state)`。
    - 优先读取 `qwen/rendered_answer.md`。
    - 如文件尚不存在但 graph state 中已有 `memo_answer.answer`，则复用 `_rendered_answer_markdown()` 生成 markdown。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加 native graph gates/render adapters 注入测试。
  - 增加 interactive graph gates/render adapters artifact 测试，验证：
    - post-gates summary 写出并回填；
    - rendered markdown 能从 graph state 生成。

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py scripts\cloud\sec_agent_graph_runner.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `20 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py::test_planner_evidence_requirements_drive_physical_routes tests\test_sec_agent_retrieval_plan.py::test_second_pass_requirements_compile_searchable_coverage_gaps tests\test_sec_agent_retrieval_plan.py::test_second_pass_stage_merges_context_and_writes_trace tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract -q`
  - `4 passed`
- native planner smoke 仍通过：
  - manifest：`data/processed_private/manifests/sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl`
  - `status=completed`
  - `node_count=15`
  - `scope_mode=sector_representative`
  - `search_scope_count=78`
  - `focus_count=5`
  - `retrieval_routes=8k_commentary=4, filing_text=4, ledger_first=4, market_snapshot=4, risk_text=1`

### 当前边界

- `verify_claims` 还没有被拆成独立真实 adapter；当前 claim verification 仍由 synthesis adapter 内部执行并写入 state，`verify_claims` node 读取已有 state。
- runner 还没有新增真实 full-native 入口，因此当前 API 调用链仍需通过 legacy interactive 或未来新增入口触发。
- 尚未跑真实 API full-native run。

### 下一步

1. 拆出独立 `verify_claims_for_graph()`，让 synthesis node 只负责模型生成和 answer normalization。
2. 新增 `--native-full-run-dir` 或等价入口，显式注入 synthesis、verify、gates、renderer，并要求 API key。
3. 用小范围 prompt 跑一次真实 full-native DeepSeek smoke，对比 legacy run 的 artifacts 和最终输出。

## 2026-05-28 Phase 8 Full-Native Runner Entry 实施记录

本轮新增显式 full-native runner 入口，用于后续真实 API 全链路测试。该入口和 `--native-ledger-smoke-dir` 分开，避免确定性 smoke 在没有 API key 的环境下误触发模型调用。

### 已实现

- `scripts/cloud/sec_agent_graph_runner.py`
  - 新增参数：`--native-full-run-dir`。
  - `--native-ledger-smoke-dir` 保持原语义：planner、retrieval、market attach、ledger、coverage、second-pass、judgment plan。
  - `--native-full-run-dir` 额外注入：
    - `synthesize_answer_for_graph`
    - `run_deterministic_gates_for_graph`
    - `render_answer_for_graph`
  - summary 增加：
    - `mode`
    - `memo_answer.answer_status`
    - `memo_answer.claim_status`
    - `deterministic_gates`
    - `rendered_answer_chars`

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py scripts\cloud\sec_agent_graph_runner.py`
- `python scripts\cloud\sec_agent_graph_runner.py --help`
  - 已显示 `--native-full-run-dir`。
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `20 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py::test_planner_evidence_requirements_drive_physical_routes tests\test_sec_agent_retrieval_plan.py::test_second_pass_requirements_compile_searchable_coverage_gaps tests\test_sec_agent_retrieval_plan.py::test_second_pass_stage_merges_context_and_writes_trace tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract -q`
  - `4 passed`
- native planner smoke 仍通过：
  - manifest：`data/processed_private/manifests/sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl`
  - `status=completed`
  - `node_count=15`
  - `scope_mode=sector_representative`
  - `search_scope_count=78`
  - `focus_count=5`
  - `retrieval_routes=8k_commentary=4, filing_text=4, ledger_first=4, market_snapshot=4, risk_text=1`

### 当前边界（Phase 8 当时）

- full-native DeepSeek/API smoke 尚未执行；需要配置 API key、BGE/CUDA 和完整数据路径后跑。
- `verify_claims` 独立 adapter 在 Phase 8 尚未拆出，已在 Phase 9 解决。

### 下一步

1. 在云端或本地 CUDA 环境跑一次小范围 `--native-full-run-dir`。
2. 如果 full-native run 通过，再把 claim verification 从 synthesis adapter 中拆出来，做到真正 node 级 checkpoint。
3. 对比 full-native 与 legacy interactive 的 run artifact，确认答案、gate 和 rendered markdown 语义一致。

## 2026-05-29 Phase 9 Verify Claims Node Checkpoint 实施记录

本轮把 claim verification 从 `synthesize_answer_for_graph()` 内部拆出来，变成 native LangGraph 的独立 `verify_claims` 节点。现在 full-native graph 中 synthesis 只负责模型生成、答案解析和未校验 memo 落盘；claim-first 校验由下一节点执行，并写回独立 checkpoint/artifact。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - 新增 `VerifyClaimsFunc`。
  - `build_native_orchestration_graph()` / `build_native_state_smoke_graph()` 增加 `verify_claims` adapter 参数。
  - `verify_claims` node 支持注入真实 adapter，写回：
    - `memo_answer`
    - `claim_verification`
    - `artifact_refs.claim_verification`
  - node trace 增加：
    - `mode=injected`
    - `status`
    - `unsupported_claim_count`
  - `synthesize_answer` node 不再接受/写回 `claim_verification`，避免 claim 校验继续作为 synthesis 的副作用。

- `scripts/cloud/sec_agent_interactive.py`
  - `synthesize_answer_for_graph()` 现在只生成未校验答案：
    - `claim_status=not_verified`
    - `claims=[]`
    - `unsupported_claim_count=0`
    - `score_notes` 增加 `claim_first_pending_native_verify_node`
  - 新增 `verify_claims_for_graph(args, graph_state)`。
    - 从 graph state 或 `qwen/trace_logs.jsonl` 读取 synthesis 使用的 context rows。
    - 从 graph state 或 `runtime_exact_value_ledger.json` 读取 ledger rows。
    - 从 `memo_answer.debug.raw_answer` 或 `qwen/raw_model_outputs.jsonl` 读取 raw parsed answer。
    - 调用现有 `verify_answer_claims()`。
    - 重写 `qwen/agent_outputs.jsonl`、`qwen/claim_verification.jsonl`、`qwen/scores.jsonl`、`qwen/rendered_answer.md` 等输出，使后续 gates 读取的是已校验答案。

- `scripts/cloud/sec_agent_graph_runner.py`
  - `--native-full-run-dir` 现在注入 `verify_claims_for_graph()`。
  - full-native 执行顺序变为：
    - `synthesize_answer`
    - `verify_claims`
    - `run_deterministic_gates`
    - `render_answer`

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加 native graph `verify_claims` adapter 注入测试。
  - 修改 synthesis adapter 测试，确认 synthesis 后 claim 状态仍为 `not_verified`，且 graph 的 stub `verify_claims` 不会伪造验证结果。
  - 增加 interactive `verify_claims_for_graph()` 测试，验证它会重写 claim artifact 和 agent output。

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py scripts\cloud\sec_agent_graph_runner.py`
- `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - `22 passed`
- `pytest tests\test_sec_agent_retrieval_plan.py::test_planner_evidence_requirements_drive_physical_routes tests\test_sec_agent_retrieval_plan.py::test_second_pass_requirements_compile_searchable_coverage_gaps tests\test_sec_agent_retrieval_plan.py::test_second_pass_stage_merges_context_and_writes_trace tests\test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract -q`
  - `4 passed`
- native planner smoke 仍通过：
  - manifest：`data/processed_private/manifests/sec_investment_coverage_mixed_with_8k_manifest_fy2023_2027.jsonl`
  - `status=completed`
  - `node_count=15`
  - `scope_mode=sector_representative`
  - `search_scope_count=78`
  - `focus_count=5`
  - `retrieval_routes=8k_commentary=4, filing_text=4, ledger_first=4, market_snapshot=4, risk_text=1`

### 当前边界

- 尚未跑真实 `--native-full-run-dir` DeepSeek/API smoke。
- `verify_claims_for_graph()` 为了复用现有输出写盘函数，会重写 qwen 输出目录；这符合当前 artifact 结构，但后续如果引入 LangGraph 原生 checkpoint store，可以把 claim report 单独落库。

### 下一步

1. 在云端或本地 CUDA 环境跑一次小范围 `--native-full-run-dir`，验证真实模型调用下 synthesis、verify、gates、renderer 串联。
2. 对比 full-native 与 legacy interactive run 的 qwen outputs、post gates 和 rendered markdown。

## 2026-05-29 Phase 10 Local Full-Native Smoke 实施记录

本轮在本地 Windows + CUDA 环境验证真实 `--native-full-run-dir`。目的不是用本机替代云端 full78 宽范围评测，而是确认小范围真实链路能在本地闭环：LangGraph native node 调度、CUDA BGE、DeepSeek synthesis、独立 `verify_claims` checkpoint、post gates 和 renderer 都能串起来。

### 已实现/修复

- 修正 post-gates 模型使用率统计：
  - `answered_api_model_truncation_repair` 等 API 模型修复态仍属于模型生成后的有效答案，不应按 fallback 处理。
  - `model_ratio` 现在按 `model_answered + model_repaired` 计算，同时保留 `model_answered` / `model_repaired` 拆分字段。
  - 新增 `model_supported_answered` 便于区分“模型原生回答数”和“模型有效回答数”。

- 本地运行参数修正：
  - 显式传入 `--bge-model BAAI/bge-reranker-v2-m3`，避免使用云端默认路径 `/root/autodl-tmp/...`。
  - 当前 full78 market evidence pack 的 `as_of_date` 为 `2026-05-27`；若传旧的 `2026-05-22` 会被严格过滤为 0 行，这是数据产品口径不匹配，不是模型问题。

### 验证

- `python -m py_compile scripts\run_sec_benchmark_post_gates.py`
- `pytest tests\test_sec_benchmark_post_gate_usage.py -q`
  - `2 passed`
- 本地小范围 full-native DeepSeek smoke：
  - output：`.tmp_native_full_smoke`
  - prompt：比较 `NVDA` 与 `AMD` 的 AI 基本面、管理层解释和市场反应
  - runtime：约 `105s`
  - `status=completed`
  - `node_count=19`
  - `market_context_row_count=2`
  - `ledger_row_count=32`
  - `coverage_complete=true`
  - `market_snapshot_support_complete=true`
  - `second_pass.triggered=true`
  - `memo_answer.answer_status=answered_api_model`
  - `memo_answer.claim_status=verified`
  - `deterministic_gates.ok=true`
  - `model_answer_ratio=1.0`

### 结论

- 本地 4060 可以跑小范围真实 full-native 链路，适合开发 smoke、节点调试和 UI 联调。
- full78 宽范围、多轮、模型 planner 和更高候选预算评测仍建议上云端跑；这不是逻辑依赖云端，而是资源和耗时问题。
- 当前 native graph 已经能完成：planner -> retrieval routes -> market attach -> ledger -> coverage -> second pass -> judgment plan -> synthesis -> verify claims -> deterministic gates -> render。

### 下一步

1. 继续把后续节点的 checkpoint 信息从 artifact-only 逐步迁移到 LangGraph state/checkpoint 语义。
2. 针对模型 planner + evidence requirement plan 跑一次 native full-chain 对照，确认模型规划下的 route、coverage 和二次检索仍稳定。
3. 后续再考虑把 session resume 从自定义 artifact resume 迁移为 LangGraph checkpointer。

## 2026-05-29 Phase 11 Node Checkpoint 与模型 planner full-chain 对照

本轮继续执行 Phase 10 后的三项下一步中的前两项：先把 native graph 后续节点的 checkpoint 摘要写入 graph state，再用模型 planner 跑一次小范围真实 full-chain 对照。目标不是为了本地资源做特化，而是确认 graph-native 调度、模型规划、证据需求、二次检索、独立 verify、gates 和 renderer 在真实链路下仍能闭环。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - 新增 `node_checkpoints` state 字段。
  - 每个 LangGraph node 完成后都会记录一个轻量 checkpoint 摘要，包括：
    - `node`
    - `index`
    - `previous_checkpoint_id`
    - `checkpoint_id`
    - `finished_at`
    - `state_summary`
    - `metadata`
  - `state_summary` 不复制大 payload，只记录可恢复和可观测所需的摘要：
    - 当前 state keys
    - artifact keys
    - `context_row_count`
    - `market_context_row_count`
    - `ledger_row_count`
    - coverage complete / sufficiency level
    - second-pass attempt count
    - answer status / claim status
    - unsupported claim count
    - deterministic gates ok
    - rendered answer length
  - 这一步仍不是最终的 LangGraph checkpointer 替换，但已经把 checkpoint 语义从“只看 artifact 是否存在”推进到“每个 node 都在 graph state 中留下可审计状态摘要”。

- `scripts/cloud/sec_agent_interactive.py`
  - 修复 `verify_claims_for_graph()` 的 context 来源优先级。
  - 旧问题：`verify_claims_for_graph()` 会优先使用 `qwen/trace_logs.jsonl` 中的 synthesis evidence pack。该文件只保留 synthesis 选中的 evidence，不一定包含 Judgment Plan 或 coverage 中引用的完整 context rows，因此真实答案中可能出现“证据存在于 graph state，但 verify 节点判定 evidence id 缺失”的误判。
  - 新逻辑：优先使用 `graph_state["context_rows"]`，只有 graph state 没有 context 时才回退到 `qwen/trace_logs.jsonl`。
  - 当 graph state context 存在时，会把完整 context rows 回写进 verify 使用的 trace payload，确保后续 artifact 与 graph state 一致。
  - 这是链路契约修复，不是 fallback：verify 节点应当校验当前 graph state 的完整证据集合，而不是只校验 synthesis 子目录里裁剪后的 evidence pack。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加 node checkpoint 断言：
    - checkpoint 数量与 node trace 对齐；
    - checkpoint schema version 正确；
    - verify / gates / renderer 节点的摘要字段可用。
  - 增加 verify context-source 测试，确认 graph state context 优先于 qwen trace context。

### 验证

- 语法检查：
  - `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_interactive.py scripts\run_sec_benchmark_post_gates.py`
- 单元测试：
  - `pytest tests\test_sec_agent_langgraph_orchestrator.py tests\test_sec_benchmark_post_gate_usage.py -q`
  - `24 passed`

- 本地小范围模型 planner full-native DeepSeek smoke：
  - output：`.tmp_native_full_smoke_llm_fixed`
  - prompt：比较 `NVDA` 与 `AMD` 的 AI 基本面、管理层解释和市场反应
  - planner：`llm:deepseek:ok`
  - runtime：约 `200s`
  - `status=completed`
  - `mode=native-full-run`
  - `node_count=19`
  - `node_checkpoints=19`
  - `scope_mode=focused_peer`
  - `search_scope_count=2`
  - `focus_count=2`
  - `retrieval_routes=8k_commentary=1, filing_text=3, ledger_first=2, market_snapshot=1, risk_text=1`
  - `context_row_count=202`
  - `market_context_row_count=2`
  - `ledger_row_count=43`
  - `coverage_complete=true`
  - `primary_task_support_complete=true`
  - `market_snapshot_support_complete=true`
  - `second_pass.triggered=true`
  - `second_pass.request_count=3`
  - `second_pass.added_context_row_count=5`
  - `sufficiency_level=sufficient`
  - `memo_answer.answer_status=answered_api_model`
  - `memo_answer.claim_status=verified`
  - `unsupported_claim_count=0`
  - `deterministic_gates.ok=true`
  - `model_answer_ratio=1.0`
  - `rendered_answer_chars=3400`

### 观察

- 模型 planner 在新链路下可以正常输出 focused peer scope、route 和 evidence requirement；没有回退到 heuristic planner。
- 二次检索会在 coverage / sufficiency 判断后自动触发，触发结果合并回 context，再继续进入 judgment plan 和 synthesis。
- verify 节点修复后，claim verification 从 `partially_verified` 恢复为 `verified`，说明之前的问题是 artifact 子集与 graph state 完整证据集合不一致，而不是模型输出或证据本身缺失。
- 最终答案已经能融合 SEC 10-K / 10-Q、8-K 管理层解释和 market snapshot，并保留市场快照日期与证据边界。

### 当前边界

- `node_checkpoints` 目前仍存在于单次 graph state / summary 中，还没有接入 SQLite / Postgres / Redis 等 LangGraph 原生持久化 checkpointer。
- 本轮 full-chain smoke 是小范围 focused peer，本地适合验证节点闭环；full78 宽范围、多行业和更高候选预算仍需要云端或更长本地运行窗口。
- session resume 仍主要依赖现有 artifact resume；尚未迁移到 LangGraph checkpointer。

### 下一步

1. 评估是否把 `node_checkpoints` 同步写入一个小型 checkpoint artifact，作为接入 SQLite checkpointer 前的过渡审计层。
2. 在云端跑一次 broad / full78 的模型 planner native full-chain，对比本地 focused peer 的 route、coverage 和二次检索稳定性。
3. 进入 session resume 迁移设计：先定义 LangGraph checkpointer 的 state schema、payload 摘要、artifact digest 引用和恢复边界，再替换当前自定义 artifact resume。

## 2026-05-29 Phase 12 Checkpoint Artifact 与 Resume 迁移设计

本轮评估 `node_checkpoints` 是否需要同步写入小型 artifact，并开始设计从自定义 artifact resume 迁移到 LangGraph checkpointer 的状态契约。结论是：需要做一个过渡审计 artifact，但它必须保持“摘要型”，不能变成第二份完整 state store。

### 结论：保留小型 checkpoint artifact

决定新增 `langgraph_node_checkpoints.json`，原因如下：

- 它可以让 CLI、workbench 和 readiness 脚本不读取 1MB+ 的 `langgraph_native_summary.json` 就能判断 node 执行顺序、最后成功节点、artifact digest 和证据覆盖摘要。
- 它为 SQLite checkpointer 之前的过渡期提供稳定审计面，便于对比 artifact resume 与 graph checkpoint resume。
- 它不复制 `context_rows`、`runtime_ledger_rows`、`coverage_matrix` 等大 payload，只保存摘要、digest 和 artifact 引用，因此不会扩大状态一致性问题。
- 它不是最终的 resume store；真正 resume 仍应由 LangGraph checkpointer 负责状态快照，由 artifact store 负责大对象。

### 已实现

- `src/sec_agent/langgraph_orchestrator.py`
  - 新增 `NODE_CHECKPOINT_ARTIFACT_SCHEMA_VERSION = sec_agent_langgraph_node_checkpoint_artifact_v0.1`。
  - `persist_session_state` 现在会写出：
    - `langgraph_node_checkpoints.json`
    - `langgraph_native_summary.json`
  - `artifact_refs` 增加：
    - `node_checkpoints`
    - `langgraph_native_summary`
  - `langgraph_node_checkpoints.json` 包含：
    - `run_id`
    - `status`
    - `output_dir`
    - `checkpoint_count`
    - `latest_checkpoint_id`
    - `latest_completed_node`
    - `payload_policy`
    - `artifact_refs`
    - `recoverable_state_summary`
    - `node_checkpoints`
  - artifact refs 对普通 artifact 计算 digest；对 `node_checkpoints` 和 `langgraph_native_summary` 这类自引用输出标记 `self_referential=true`，不计算自 digest，避免写入顺序导致误导。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加 checkpoint artifact 写出和 schema 断言。
  - 验证 artifact 是 summary-only，且自引用 artifact 标记正确。

- `scripts/cloud/sec_agent_graph_runner.py`
  - 新增 `--inspect-native-checkpoints <path-or-run-dir>`。
  - 该入口只读取 `langgraph_node_checkpoints.json`，不会重跑链路。
  - 输出：
    - `latest_completed_node`
    - `next_recoverable_node`
    - `required_artifacts_for_next_node`
    - `resume_supported`
    - `blocked_reasons`
    - `missing_required_artifacts`
    - `digest_mismatch_artifacts`
    - `artifact_status`

- `src/sec_agent/langgraph_orchestrator.py`
  - 新增 `inspect_node_checkpoint_artifact()`。
  - 新增 native resume 只读判断逻辑：
    - 从最近成功 node 推导下一个 recoverable node。
    - 对下一节点所需 artifact 做 exists / digest 校验。
    - 完成态 run 返回 `no_next_node`，不误报为可恢复。

### LangGraph Checkpointer State Schema v1 草案

SQLite checkpointer 接入后，每个成功 node 的 checkpoint 应保存以下逻辑字段。具体底层表可以沿用 LangGraph saver，但业务 payload 需要保持这个契约。

| 字段 | 说明 |
|---|---|
| `checkpoint_id` | 当前 checkpoint 的稳定 id，由 run、node、index、state summary digest 生成 |
| `parent_checkpoint_id` | 上一个成功 node checkpoint |
| `thread_id` | LangGraph thread id，对应 session/thread |
| `run_id` | 当前 run id |
| `session_identity` | tenant、user、session、thread、turn，后续从 workbench/API 传入 |
| `node_name` | 成功完成的 graph node |
| `node_index` | graph 内完成序号 |
| `created_at` | checkpoint 写入时间 |
| `state_schema_version` | `sec_agent_graph_runtime_state_v1` |
| `state_summary` | 小摘要：status、state keys、row count、coverage、sufficiency、claim/gate/render 状态 |
| `artifact_refs` | 大 payload 的 path、digest、schema、row count、source role |
| `resume_boundary` | 从该 checkpoint 恢复时允许进入的下一个 node 和需要校验的 artifact |
| `telemetry` | node 耗时、候选数、BGE 数、token、错误摘要 |

大 payload 仍不直接写进 checkpoint：

- `context_rows` 使用 `trace/trace_logs.jsonl` 或后续独立 evidence store。
- `market_snapshot_rows` 使用 `market_snapshot_context_rows.jsonl`。
- `runtime_ledger_rows` 使用 `runtime_exact_value_ledger.json` 或 DuckDB lightweight ledger store。
- `coverage_matrix`、`judgment_plan`、`memo_answer`、`claim_verification`、`deterministic_gates`、`rendered_answer` 使用各自 artifact。

### Artifact 引用契约

每个 artifact ref 需要至少包含：

```json
{
  "key": "runtime_exact_value_ledger",
  "path": ".../runtime_exact_value_ledger.json",
  "schema_version": "sec_agent_runtime_exact_value_ledger_v0.1",
  "row_count": 32,
  "digest": "sha256-16",
  "source_role": "runtime_ledger",
  "required_for_resume_after": ["build_runtime_ledger", "assess_evidence_coverage"]
}
```

恢复时先校验 digest：

- digest 一致：加载 artifact，进入下一个 node。
- digest 缺失或不一致：不信任该 checkpoint 对应的后续状态，从能重建该 artifact 的上游 node 重新执行。
- artifact 是自引用审计文件：不作为业务恢复依赖。

### 恢复边界

可恢复边界只放在成功完成的 node 之后；执行中的 BGE、LLM call、post-gates 文件写入不作为 checkpoint 边界。

| 最近成功 node | 恢复动作 |
|---|---|
| `plan_query` | 校验 query contract / retrieval plan；从 `execute_retrieval_routes` 继续 |
| `execute_retrieval_routes` | 校验 retrieved context；从 `attach_market_snapshot` 继续 |
| `attach_market_snapshot` | 校验 market context；从 `build_runtime_ledger` 继续 |
| `build_runtime_ledger` | 校验 ledger；从 `assess_evidence_coverage` 继续 |
| `assess_evidence_coverage` | 校验 coverage；进入 sufficiency 或 second-pass 分支 |
| `execute_second_pass_retrieval` | 校验 second-pass context；重建 ledger 和 coverage |
| `build_judgment_plan` | 校验 judgment plan；从 `synthesize_answer` 继续 |
| `synthesize_answer` | 校验 raw/memo artifact；从 `verify_claims` 继续 |
| `verify_claims` | 校验 claim report；从 `run_deterministic_gates` 继续 |
| `run_deterministic_gates` | 校验 gate summary；从 `render_answer` 继续 |
| `render_answer` | 校验 rendered answer；进入 `persist_session_state` |

### 替换自定义 artifact resume 的执行步骤

1. **过渡审计层**：已完成。native graph 写 `langgraph_node_checkpoints.json`，readiness 可以读取它判断 graph-native node 状态。
2. **Native resume inspector**：新增读取 `langgraph_node_checkpoints.json` 的 inspect 入口，输出 next node、artifact digest 状态和不可恢复原因；先不执行重跑。
3. **SQLite checkpointer 接入**：新增 `SEC_AGENT_CHECKPOINTER=memory|sqlite`，默认本地开发仍可 memory，真实 session 使用 SQLite。
4. **State hydration**：从 checkpoint + artifact refs 重建 graph state 摘要和必要 payload；大 payload 只在即将进入对应 node 前加载。
5. **Graph-native resume executor**：从最近成功 checkpoint 进入下一个 node，不再用 `state_resume_report(sec_agent_state)` 推断阶段。
6. **兼容期**：legacy `sec_agent_state.json` resume 保留给旧 CLI；workbench 和新 native runner 默认走 LangGraph checkpointer。
7. **移除条件**：当 retrieval、ledger、synthesis、verify、gates、render 的中断恢复 smoke 都通过后，再把自定义 artifact resume 降级为只读兼容工具。

### 本地真实中小 smoke

本轮执行了一个不调用 LLM 的真实 native ledger smoke，用于验证 checkpoint artifact 能跟随真实检索链路落盘。

- output：`.tmp_langgraph_checkpoint_smoke`
- prompt：比较 `NVDA` 和 `AMD` 的 AI 基本面、管理层解释和市场反应
- mode：`native-ledger-smoke`
- planner：`heuristic:ok`
- runtime：约 `50s`
- `status=completed`
- `node_count=19`
- `checkpoint_count=19`
- `latest_completed_node=persist_session_state`
- `context_row_count=127`
- `market_context_row_count=2`
- `ledger_row_count=32`
- `coverage_complete=true`
- `market_snapshot_support_complete=true`
- `second_pass.triggered=true`
- `second_pass.request_count=2`
- `second_pass.added_context_row_count=10`
- `judgment_plan.has_plan=true`
- `artifact_refs` 包含 `node_checkpoints` 和 `langgraph_native_summary`
- `langgraph_node_checkpoints.json` 大小约 `37KB`，而完整 `langgraph_native_summary.json` 约 `1.8MB`
- inspector 检查：
  - `python scripts\cloud\sec_agent_graph_runner.py --inspect-native-checkpoints .tmp_langgraph_checkpoint_smoke`
  - `latest_completed_node=persist_session_state`
  - `next_recoverable_node=""`
  - `resume_supported=false`
  - `blocked_reasons=["no_next_node"]`
  - 普通业务 artifact digest 校验通过

### 当前边界

- 本轮 smoke 不调用 synthesis API，因此没有验证 `synthesize_answer -> verify_claims -> gates -> render` 的模型输出质量；这部分上一轮小范围 full-native smoke 已验证过，后续需要在云端或本地 API 环境再跑一次带 SQLite checkpointer 的 full-native run。
- 目前 checkpoint artifact 和 inspector 是审计与恢复判断层，不直接恢复执行；下一步接 SQLite checkpointer 后，再让 native graph 从 checkpoint 进入下一个 node。

### 下一步

1. 接入 SQLite checkpointer 配置，但先只在 native graph runner 中启用，不影响 legacy runner。
2. 用 checkpoint inspector 构造 retrieval 后、ledger 后、synthesis 后、gate 后四类 partial checkpoint fixture，先验证 next node 和 artifact digest 判断。
3. 做 retrieval 后、ledger 后、synthesis 后、gate 后四个中断恢复 smoke，确认 graph-native resume 能替代当前自定义 artifact resume。

## 2026-05-29 Phase 13：SQLite checkpointer 轻量化写入

### 问题

初版 SQLite checkpointer 能跑通 native graph，但默认 LangGraph saver 会把完整 state 写进 `checkpoints` 和 `writes` 表。中型 `native-ledger-smoke` 中，`context_rows`、`retrieval_trace`、`project_inventory`、`runtime_ledger_rows` 等大对象在每个 node 后重复序列化，导致单次 run 的 `langgraph_checkpoints.sqlite` 约 `39.5MB`。

这和前面定义的恢复契约冲突：checkpoint 应保存可恢复摘要、node 边界和 artifact digest；完整证据、ledger、coverage、memo 等大 payload 应留在各自 artifact 或后续 store 中。

### 实现

- `src/sec_agent/langgraph_orchestrator.py`
  - 新增 `SlimmingCheckpointSaver`。
  - 包装 LangGraph checkpointer 的 `put()` 和 `put_writes()`。
  - 在写入 checkpoint 前将大 channel 替换为外部 payload 摘要：
    - `context_rows`
    - `market_snapshot_rows`
    - `runtime_ledger_rows`
    - `coverage_matrix`
    - `retrieval_trace`
    - `project_inventory`
    - `judgment_plan`
    - `memo_answer`
    - `claim_verification`
    - `deterministic_gates`
    - `rendered_answer`
  - 摘要保留：
    - channel 名称
    - value 类型
    - summary digest
    - row_count / key_count / char_count
    - sample keys / sample ids
    - coverage summary 等小型业务摘要
  - 完整 payload 完整性校验仍依赖 artifact refs 的文件 digest，避免 checkpoint 层为了摘要再重复序列化大型证据包。

- `scripts/cloud/sec_agent_graph_runner.py`
  - native runner 的 `memory` 和 `sqlite` checkpointer 统一经过 `wrap_checkpoint_saver_for_sec_agent_state()`。
  - legacy `sec_agent_state.json` resume 路径不受影响。

- `langgraph_native_summary.json`
  - 从完整 state dump 改成真正 summary artifact。
  - 仍保留 `node_trace`、`node_checkpoints`、`artifact_refs`、`artifact_status` 和 `state_summary`。
  - 不再写入完整 `context_rows` / `runtime_ledger_rows` / 大型 retrieval payload。

### 验证

- 单测：
  - `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_graph_runner.py`
  - `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - 结果：`24 passed`

- 新增单测：
  - `test_native_sqlite_checkpointer_externalizes_large_payloads`
  - 验证 graph 返回值仍保留完整 `context_rows`，但 SQLite checkpoint 中的 `context_rows` 已变成 `externalized_summary`。

- 本地真实中型 smoke：
  - output：`.tmp_langgraph_sqlite_ledger_smoke_slim`
  - mode：`native-ledger-smoke`
  - checkpointer：`sqlite`
  - scope：`NVDA, AMD`
  - source：10-K / latest 10-Q / 8-K / market snapshot
  - planner：`heuristic:ok`
  - `status=completed`
  - `node_count=19`
  - `context_row_count=118`
  - `market_context_row_count=2`
  - `ledger_row_count=24`
  - `coverage_complete=true`
  - `primary_task_support_complete=true`
  - `second_pass.triggered=true`
  - `judgment_plan.has_plan=true`

- SQLite 体积对比：
  - 优化前：`.tmp_langgraph_sqlite_ledger_smoke/langgraph_checkpoints.sqlite` 约 `39.5MB`
  - 优化后：`.tmp_langgraph_sqlite_ledger_smoke_slim/langgraph_checkpoints.sqlite` 约 `2.2MB`
  - `checkpoints` blob 总量：约 `19.6MB -> 1.0MB`
  - `writes` blob 总量：约 `19.6MB -> 1.0MB`

- summary artifact：
  - `.tmp_langgraph_sqlite_state_smoke_slim/langgraph_native_summary.json` 约 `22KB`
  - `.tmp_langgraph_sqlite_state_smoke_slim/langgraph_node_checkpoints.json` 约 `20KB`
  - `.tmp_langgraph_sqlite_state_smoke_slim/langgraph_checkpoints.sqlite` 约 `455KB`

### 当前边界

- 这是 checkpoint 存储层轻量化，不等同于完整 resume 执行器。
- 直接从 LangGraph SQLite checkpoint 恢复时，部分 channel 是摘要，不是完整 payload；后续必须先做 state hydration，从 artifact refs 读取必要 payload，再进入下一个业务 node。
- 这个设计是有意的：避免把 SQLite checkpointer 变成重复保存大型证据包的第二套对象仓库。

### 下一步

1. 定义 `hydrate_native_state_from_checkpoint()`：从 latest checkpoint + `artifact_refs` 按 next node 需要加载最小 payload。
2. 做 partial checkpoint fixture：retrieval 后、ledger 后、synthesis 后、gate 后。
3. 加 `--resume-native-checkpoint` 只跑 graph-native resume smoke，先覆盖 retrieval 后和 ledger 后两个边界。
4. 再把 synthesis / verify / gates / render 的中断恢复迁入 native resume。

## 2026-05-29 Phase 14：Checkpoint Hydration 初版

### 实现

- `src/sec_agent/langgraph_orchestrator.py`
  - 新增 `hydrate_native_state_from_checkpoint_artifact(path)`。
  - 输入可以是 `langgraph_node_checkpoints.json` 或 partial checkpoint artifact。
  - 输出：
    - `latest_completed_node`
    - `next_recoverable_node`
    - `resume_supported`
    - `blocked_reasons`
    - `state`
    - `state_summary`
    - `artifact_status`
  - hydration 会从 artifact refs 读取：
    - `case` -> `user_query`、`query_contract`、ticker/year scope
    - `retrieval_plan`
    - `retrieved_context`
    - `market_snapshot_context`
    - `runtime_exact_value_ledger`
    - `evidence_coverage_matrix`
    - `second_pass_retrieval_trace`
    - `judgment_plan`
    - 后续 synthesis / verification / gates / rendered answer artifact

- `scripts/cloud/sec_agent_graph_runner.py`
  - 新增 `--hydrate-native-checkpoints <path-or-run-dir>`。
  - 只做恢复状态装载和摘要打印，不重跑业务节点。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 新增 `test_native_checkpoint_hydrates_retrieval_boundary`。
  - 构造 run 后截断到 `execute_retrieval_routes`，验证：
    - `next_recoverable_node=attach_market_snapshot`
    - `resume_supported=true`
    - `context_rows` 可以从 artifact 重新装载。

### 暴露并修复的问题

真实中型 run 的 partial hydration 第一次只恢复出 3 行 context，而原始 state 有 118 行。原因不是 checkpointer，而是 artifact 读取语义：

- `retrieved_context` 指向 `trace/trace_logs.jsonl`。
- 该文件每一行是 trace event，不是直接的 evidence row。
- 真正 evidence rows 在 trace event 的 `context_rows` 字段中。

修复：

- 新增 `_load_context_rows_ref()`。
- 如果 JSONL 行里包含 `context_rows`，hydration 展开该字段作为证据行。
- 如果 JSONL 本身就是 evidence row 列表，则保持原行为。

### 验证

- 单测：
  - `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_graph_runner.py`
  - `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - 结果：`25 passed`

- 真实中型 partial checkpoint：
  - source run：`.tmp_langgraph_sqlite_ledger_smoke_slim`
  - partial artifact：`.tmp_langgraph_sqlite_ledger_smoke_slim/partial_build_runtime_ledger_checkpoint.json`
  - latest node：`build_runtime_ledger`
  - next node：`assess_evidence_coverage`
  - `resume_supported=true`
  - hydrated `context_row_count=118`
  - hydrated `market_context_row_count=2`
  - hydrated `ledger_row_count=24`
  - artifact digest 检查通过

### 当前边界

- hydration 已能重建进入下一个 node 所需的主要 payload，但还没有真正调用 graph 从该 node 继续执行。
- 当前 partial artifact 是由完整 run 截断生成；下一步需要加入可控中断参数，让真实 run 在指定 node 后停止并直接写 partial checkpoint。
- synthesis / verify / gates / render 边界还需要分别做 hydration smoke。

### 下一步

1. 加 native graph 的 `stop_after_node` 或 runner-level partial checkpoint smoke，避免手工截断。
2. 增加 `--resume-native-checkpoint`，从 hydrated state 进入下一个 node 执行。
3. 先覆盖 `execute_retrieval_routes -> attach_market_snapshot` 和 `build_runtime_ledger -> assess_evidence_coverage` 两个恢复边界。
4. 再覆盖 `synthesize_answer -> verify_claims`、`verify_claims -> run_deterministic_gates`、`run_deterministic_gates -> render_answer`。

## 2026-05-29 Phase 15：Native Resume Executor 初版

### 实现

- `src/sec_agent/langgraph_orchestrator.py`
  - `build_native_orchestration_graph()` / `build_native_state_smoke_graph()` 新增 `entry_node` 参数。
  - 默认仍从 `load_session_state` 开始。
  - resume 时可以把 LangGraph 入口切到 `next_recoverable_node`，例如 `assess_evidence_coverage`。

- `scripts/cloud/sec_agent_graph_runner.py`
  - 新增 `--resume-native-checkpoint <path>`。
  - 执行顺序：
    1. 读取 checkpoint artifact。
    2. 校验 required artifact digest。
    3. hydration 重建最小 graph state。
    4. 用 `entry_node=next_recoverable_node` 编译 native graph。
    5. 从该 node 继续执行。
  - 默认不执行 synthesis / verify / gates / renderer 的真实模型和后处理 adapter；用于本地确定性恢复 smoke。
  - 如需跑模型后半段，可显式加 `--native-resume-include-synthesis`。

### 验证

- 单测：
  - `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_graph_runner.py`
  - `pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - 结果：`25 passed`

- 单测 resume 边界：
  - `test_native_checkpoint_hydrates_retrieval_boundary`
  - 从截断到 `execute_retrieval_routes` 的 checkpoint hydrate。
  - 以 `entry_node=attach_market_snapshot` 继续执行到完成。

- 真实中型 resume smoke：
  - checkpoint：`.tmp_langgraph_sqlite_ledger_smoke_slim/partial_build_runtime_ledger_checkpoint.json`
  - entry node：`assess_evidence_coverage`
  - `status=completed`
  - `context_row_count=118`
  - `market_context_row_count=2`
  - `ledger_row_count=24`
  - `coverage_complete=true`
  - `primary_task_support_complete=true`
  - `judgment_plan.has_plan=true`
  - 本次没有重新做 BGE 检索，恢复从 ledger 后的确定性节点继续。

### 当前边界

- partial checkpoint 目前仍是手工截断 artifact 得到；还需要 runner 支持 `--native-stop-after-node` 生成真实中断 fixture。
- synthesis / verify / gates / render 的恢复执行还没做真实模型 smoke。
- 旧 `sec_agent_state.json` resume 还未替换；当前 native resume executor 是并行新入口。

### 下一步

1. 加 `--native-stop-after-node`，让 native run 可以真实停止在指定 node 后并写 checkpoint。
2. 跑 retrieval 后和 ledger 后两个自动中断恢复 smoke。
3. 给 synthesis / verify / gates / render 增加 artifact hydration 和恢复测试。
4. workbench/API resume 入口切到 native checkpoint，legacy artifact resume 保留为兼容检查。

## 2026-05-29 Phase 16：Native Stop-After-Node 与真实 partial checkpoint

### 实现

- `src/sec_agent/langgraph_orchestrator.py`
  - `build_native_orchestration_graph()` / `build_native_state_smoke_graph()` 新增 `stop_after_node` 参数。
  - 每个 native node 仍先正常执行并写入 `node_trace` / `node_checkpoints`。
  - 如果当前 node 等于 `stop_after_node`，graph state 会标记：
    - `status=stopped_after_node`
    - `native_stop_after_node=<node>`
  - 随后立即写出：
    - `langgraph_node_checkpoints.json`
    - `langgraph_native_summary.json`
  - graph 通过条件边进入 `END`，不是外部 kill，也不是手工截断 artifact。

- `scripts/cloud/sec_agent_graph_runner.py`
  - 新增 `--native-stop-after-node <node>`。
  - 支持 native state / plan / retrieval / ledger / full-run / resume 入口。
  - 输出 summary 中增加 `native_stop_after_node`，便于 smoke 和 workbench 判断这次 run 是自然完成还是有意中断。

### 验证

- 单测：
  - `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_graph_runner.py`
  - `python -m pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
  - 结果：`26 passed`

- 新增单测：
  - `test_native_stop_after_node_writes_real_partial_checkpoint`
  - 覆盖：
    - stop after `execute_retrieval_routes`
    - 自动写 `langgraph_node_checkpoints.json`
    - inspector 判断 `next_recoverable_node=attach_market_snapshot`
    - hydration 恢复 `context_rows`
    - resume graph 从 `attach_market_snapshot` 继续到完成

- 本地真实小链路 smoke：
  - run dir：`.tmp_native_stop_ledger_smoke`
  - prompt：比较 `NVDA` / `AMD` 最近披露中 AI 相关收入、管理层解释和市场快照的差异
  - scope：`tickers=NVDA,AMD`，`years=2026`
  - reranker：本地 `D:\hf_cache\hub\models--BAAI--bge-reranker-v2-m3\snapshots\953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`
  - device：`cuda`
  - checkpoint backend：`sqlite`
  - stop node：`build_runtime_ledger`
  - 结果：
    - `status=stopped_after_node`
    - `node_count=7`
    - `context_row_count=96`
    - `ledger_row_count=23`
    - `context_resource_load_ms=28990`
    - `context_runtime.elapsed_ms=34168`
    - SQLite checkpoint：约 `430KB`
    - `langgraph_node_checkpoints.json`：约 `10KB`
    - `langgraph_native_summary.json`：约 `12KB`

- Partial checkpoint inspect / hydrate：
  - `latest_completed_node=build_runtime_ledger`
  - `next_recoverable_node=assess_evidence_coverage`
  - required artifacts：
    - `retrieved_context`
    - `runtime_exact_value_ledger`
  - `resume_supported=true`
  - digest 检查通过
  - hydrated `context_row_count=96`
  - hydrated `ledger_row_count=23`

- Resume smoke：
  - command 使用 `--resume-native-checkpoint .tmp_native_stop_ledger_smoke`
  - entry node：`assess_evidence_coverage`
  - stop node：`assess_evidence_coverage`
  - 结果：
    - `status=stopped_after_node`
    - `node_count=8`
    - `coverage_complete=true`
    - `primary_task_support_complete=true`
    - `answer_status=complete`
  - 该恢复只执行 coverage 节点，没有重新跑 BGE 检索。

### 当前边界

- 本轮证明了真实 partial checkpoint 可以由 graph 自然产生，并可从 ledger 后恢复到 coverage。
- 本轮没有跑带 LLM synthesis 的恢复 smoke；`synthesize_answer -> verify_claims -> gates -> render` 的 checkpoint 边界仍需单独验证。
- 小链路 smoke 中 heuristic planner 没有把 market snapshot 纳入 coverage 要求，因此本次验证只用于 checkpoint/resume，不作为 full-source 输出质量证据。

### 下一步

1. 补 `synthesize_answer -> verify_claims`、`verify_claims -> run_deterministic_gates`、`run_deterministic_gates -> render_answer` 三个恢复边界的 artifact hydration 测试。
2. 让 workbench 的 session resume 入口优先读取 native checkpoint inspection，legacy `sec_agent_state.json` resume 作为兼容路径。
3. 再跑一次带 API 模型的小范围 native full-run，验证 SQLite checkpointer + stop/resume + 独立 verify 节点在模型后半段仍稳定。

## 2026-05-29 Phase 17：后半段 checkpoint hydration 边界测试

### 实现

- `src/sec_agent/langgraph_orchestrator.py`
  - hydration 增加 `memo_answer` 恢复。
  - 新增 `_load_json_or_first_jsonl_ref()`，用于读取既可能是 JSON、也可能是单行/多行 JSONL 的 artifact。
  - `claim_verification` 也改为该读取方式，匹配当前 interactive adapter 中 `claim_verification.jsonl` 的真实形态。

- `tests/test_sec_agent_langgraph_orchestrator.py`
  - 增加小型 artifact fixture 写入工具：
    - `case.jsonl`
    - `trace/trace_logs.jsonl`
    - `runtime_exact_value_ledger.json`
    - `runtime_evidence_coverage_matrix.json`
    - `runtime_judgment_plan.json`
  - 新增三段恢复边界测试：
    - `test_native_resume_boundary_synthesis_to_verify_claims`
    - `test_native_resume_boundary_verify_claims_to_gates`
    - `test_native_resume_boundary_gates_to_render`

### 覆盖的恢复边界

1. `synthesize_answer -> verify_claims`
   - stop after `synthesize_answer`
   - checkpoint artifact 包含 `memo_answer`
   - inspect 输出 `next_recoverable_node=verify_claims`
   - hydration 恢复 `memo_answer`、`context_rows`、`runtime_ledger_rows`
   - resume 后执行 `verify_claims`

2. `verify_claims -> run_deterministic_gates`
   - stop after `verify_claims`
   - checkpoint artifact 包含 `claim_verification`
   - inspect 输出 `next_recoverable_node=run_deterministic_gates`
   - hydration 恢复 `claim_verification`
   - resume 后执行 deterministic gates

3. `run_deterministic_gates -> render_answer`
   - stop after `run_deterministic_gates`
   - checkpoint artifact 包含 `deterministic_gates`
   - inspect 输出 `next_recoverable_node=render_answer`
   - hydration 恢复 `deterministic_gates`
   - resume 后执行 renderer

### 验证

- `python -m py_compile src\sec_agent\langgraph_orchestrator.py scripts\cloud\sec_agent_graph_runner.py`
- `python -m pytest tests\test_sec_agent_langgraph_orchestrator.py -q`
- 结果：`29 passed`

### 当前边界

- 本轮使用 stub adapter 验证 checkpoint / hydration / resume contract，没有调用 API 模型。
- 已覆盖后半段 artifact 恢复语义，但还没有把 workbench/API 的 resume 按钮切到 native checkpoint inspector。
- 还需要一次带 API 模型的小范围 native full-run，验证真实 `memo_answer -> verify_claims -> gates -> render` artifact 在同一 contract 下稳定。

### 下一步

1. workbench/API resume 入口优先读取 `langgraph_node_checkpoints.json` inspection，并展示 next node、blocked reasons、artifact digest 状态。
2. legacy `sec_agent_state.json` resume 保留为兼容路径，但新 session 默认走 native checkpoint。
3. 跑一次带 API 模型的小范围 native full-run + stop/resume，验证真实后半段输出质量和 checkpoint 稳定性。

## 2026-05-29 Phase 18：Workbench/API Resume 集成预检

### 预检结果

计划继续把 workbench/API 的 resume 入口切到 native checkpoint inspection，但当前工作树中的 workbench 可编辑源码不完整：

- `apps/workbench/backend` 目前只有 `__pycache__`，没有可编辑的 `app.py` 或 router 源码。
- `scripts/workbench/start_workbench.py` 当前不存在，但本地仍有一个历史启动的 Python 进程引用该路径。
- `apps/workbench/frontend` 目前主要是 `dist`、`node_modules` 和 `vite/index.html`，没有常规 `src` 源码目录。

### 决策

本轮不从 pycache 或 dist 反推源码，也不新造一套 parallel workbench backend。这样会增加第二套入口，反而破坏当前迁移目标。

当前已具备可复用 CLI/API 底层能力：

- `--inspect-native-checkpoints <run-dir-or-file>`
- `--hydrate-native-checkpoints <run-dir-or-file>`
- `--resume-native-checkpoint <run-dir-or-file>`
- `--native-stop-after-node <node>`

等 workbench 源码恢复或确认入口文件后，再把这些能力接入已有 API，而不是绕过现有应用结构。

### 当前边界

- Workbench/UI resume 入口尚未改动。
- Native checkpoint / hydration / resume 的底层能力已通过单测和本地小链路 smoke 验证。

### 下一步

1. 恢复或确认 workbench backend/frontend 源码入口。
2. 在现有 API 中新增 native checkpoint inspection endpoint，返回 next node、resume support、blocked reasons 和 artifact digest 状态。
3. UI 只展示 inspection 和 resume 动作，不直接解析 artifact 文件。

## 2026-05-29 Phase 19：Workbench Native Checkpoint 入口接入

### 入口确认

- Workbench 正式源码在分支 `codex/workbench-plan` 的提交 `a0704a2 Add FinSight Workbench and full-source session controls`。
- 当前 `codex/api-model-call-architecture` 分支只有历史安装/构建产物残留，因此本轮只从 `a0704a2` 恢复 workbench 相关源码、配置示例、文档和测试：
  - `apps/workbench/**`
  - `src/sec_agent/workbench/**`
  - `scripts/workbench/**`
  - `docs/workbench/**`
  - `configs/sec_agent_full_source_demo.env.example`
  - `tests/test_workbench_*.py`
- 没有恢复 `a0704a2` 中对主链路脚本的旧改动，避免覆盖当前 LangGraph/native checkpoint 分支已有修改。

### 实现

- `.gitignore`
  - 忽略 `data/workbench_private/`、`node_modules/`、`dist/` 和 `reports/model_runs/*.json`。
  - 保留 `apps/workbench/frontend/index.html` 可跟踪，避免 `*.html` 规则屏蔽前端 shell。

- `src/sec_agent/workbench/job_runner.py`
  - 新增 `build_native_checkpoint_resume_command()`。
  - 通过 `scripts/cloud/sec_agent_graph_runner.py --resume-native-checkpoint <run-dir-or-file>` 启动 native resume。
  - 支持 `checkpoint_mode=memory|sqlite|none`、`include_synthesis`、`stop_after_node`。
  - 支持 local / WSL 两类 execution shell。
  - API key 只进入运行环境变量，不进入命令参数。

- `src/sec_agent/workbench/jobs.py`
  - 新增 `native_checkpoint_resume` job 类型。
  - job metadata 记录 checkpoint path、stop node 和 synthesis resume 开关。

- `apps/workbench/backend/app.py`
  - 新增 `POST /api/native-checkpoints/inspect`。
  - 新增 `POST /api/native-checkpoints/resume`。
  - inspect 直接调用 `inspect_node_checkpoint_artifact()`，返回：
    - `latest_completed_node`
    - `next_recoverable_node`
    - `resume_supported`
    - `blocked_reasons`
    - required artifact / digest 状态
  - resume 先做 inspection；不可恢复时返回 `409`，不启动后台任务。

- `apps/workbench/frontend/vite/src/main.tsx`
  - 在运行产物区新增 native checkpoint 操作：
    - 检查 Native Checkpoint
    - 从 Checkpoint 恢复
  - UI 显示 latest node、next node、checkpoint count、required artifacts 和 blocked reasons。
  - resume 使用当前 profile 和本次 API key，不保存密钥。

- `src/sec_agent/workbench/artifacts.py`
  - 运行产物检查中识别：
    - `langgraph_node_checkpoints.json`
    - `langgraph_native_summary.json`

### 验证

- Python 编译：
  - `python -m py_compile apps/workbench/backend/app.py src/sec_agent/workbench/job_runner.py src/sec_agent/workbench/jobs.py src/sec_agent/workbench/artifacts.py src/sec_agent/workbench/__init__.py`
- Workbench 单测：
  - `pytest tests/test_workbench_job_runner.py tests/test_workbench_artifacts.py tests/test_workbench_backend.py -q`
  - 结果：`29 passed`
- LangGraph native 单测：
  - `pytest tests/test_sec_agent_langgraph_orchestrator.py -q`
  - 结果：`29 passed`
- 前端构建：
  - `npm run build`
  - 结果：通过，生成 `apps/workbench/frontend/dist`
- 本地服务检查：
  - `http://127.0.0.1:8765/api/health`
  - 返回 `status=ok`，前端可用。

### 当前边界

- Workbench 现在可以查看并启动 native checkpoint resume，但仍是基于 `langgraph_node_checkpoints.json` 过渡审计层；后续要把 session resume 正式迁到 LangGraph SQLite checkpointer。
- 本轮没有跑带 API 模型的 native full-run + workbench resume；真实模型恢复 smoke 放到下一阶段。
- 浏览器自动化插件在本机提示 `browser-client is not trusted`，本轮使用 HTTP health、前端构建和单测替代 UI 自动化验证。

### 下一步

1. 用真实小范围 native full-run 生成 `langgraph_node_checkpoints.json`，在 workbench 中检查并从后半段 resume。
2. 将 workbench 的 session resume 默认路径从 artifact-only resume 切到 native checkpoint inspection。
3. 开始设计 SQLite checkpointer 的 session/thread 查询和 UI 展示方式，减少对单个 run 目录 artifact 的依赖。

## 2026-05-29 Phase 20：Workbench 自动检查与真实 full-chain 验证

### 目标

继续推进 native LangGraph 编排从“可手动检查”走向“运行入口默认可审计”：

- Workbench/API 读取 run 时自动附带 native checkpoint inspection，不再要求用户额外点一次检查按钮才知道恢复边界。
- Native node checkpoint 需要记录真实节点耗时，避免 summary 里所有 `elapsed_ms=0`，否则后续无法用它做 stage-level observability。
- 用真实 API 模型和本地 BGE 跑一个小范围 full-chain case，验证这轮改动没有破坏 `plan -> retrieval -> ledger -> coverage -> synthesis -> verify -> gates -> render`。

### 实现

- `apps/workbench/backend/app.py`
  - `GET /api/runs/{job_id}` 返回 `native_checkpoint`。
  - `POST /api/runs/inspect` 返回 `RunInspectionReport.native_checkpoint`。
  - 新增内部检查函数：如果 run 目录存在 `langgraph_node_checkpoints.json`，自动调用 native checkpoint inspector；JSON 或 schema 异常时返回结构化 invalid 状态，不让 API 整体失败。

- `src/sec_agent/workbench/jobs.py`
  - `RunInspectionReport` 增加 `native_checkpoint` 字段。

- `apps/workbench/frontend/vite/src/main.tsx`
  - `loadRun`、`refreshJob`、`inspectRun` 会直接接收后端返回的 `native_checkpoint`，进入 run 页面后即可看到 checkpoint 状态。

- `src/sec_agent/langgraph_orchestrator.py`
  - 用 `_wrap_native_node()` 替代只处理 stop-after-node 的 wrapper。
  - 每个 native node 执行时记录 `started_at` 和 `elapsed_ms`。
  - 同步更新 `node_trace` 和 `node_checkpoints`，并在 hydration 后保留这些 timing 字段。

- 测试补充：
  - `tests/test_workbench_backend.py`
    - 覆盖 `/api/runs/inspect` 和 `/api/runs/{job_id}` 自动返回 native checkpoint。
  - `tests/test_sec_agent_langgraph_orchestrator.py`
    - 覆盖 native summary / checkpoint 中 `elapsed_ms` 非零。

### 验证

- Workbench 后端与 job 测试：
  - `pytest tests/test_workbench_backend.py tests/test_workbench_artifacts.py tests/test_workbench_job_runner.py -q`
  - 结果：`31 passed`

- LangGraph native 单测：
  - `pytest tests/test_sec_agent_langgraph_orchestrator.py -q`
  - 结果：`30 passed`

- Python 编译：
  - `python -m py_compile src/sec_agent/langgraph_orchestrator.py apps/workbench/backend/app.py src/sec_agent/workbench/jobs.py`
  - 结果：通过

- 前端构建：
  - 使用仓库本地 Node：`.tmp_node/node-v24.16.0-win-x64/npm.cmd run build`
  - 结果：通过

- 真实 full-chain case：
  - 范围：`NVDA,AMD`，FY2026，full-source/native graph，小范围真实 DeepSeek API + 本地 CUDA BGE。
  - 输出目录：`.tmp_native_full_chain_nvda_amd_20260529_1525_timing`
  - 结果：`status=completed`，`node_count=19`，planner `llm:deepseek:ok`，二次检索触发并完成，coverage complete，gates pass，renderer 生成答案。
  - checkpoint 检查：`--inspect-native-checkpoints .tmp_native_full_chain_nvda_amd_20260529_1525_timing` 通过，required artifacts 存在，digest 校验通过。
  - 节点耗时已可见，例如 `plan_query`、`execute_retrieval_routes`、`synthesize_answer`、`run_deterministic_gates` 均有非零 `elapsed_ms`。

### 当前判断

- Workbench/API 已经能把 native checkpoint inspection 纳入 run inspection/report 的默认返回。
- Native checkpoint 现在不仅能恢复，也能作为 stage-level timing 的过渡审计层。
- 真实小范围 full-chain 在新 checkpoint/timing 语义下跑通，说明这轮改动没有破坏主链路。

### 当前边界

- 这仍是 artifact checkpoint 过渡层，不是最终的 LangGraph SQLite/Postgres checkpointer。
- 本轮验证了真实 full-chain 完整执行和 checkpoint inspect，没有单独跑一次真实 stop/resume API 模型恢复。
- Full78 宽范围 retrieval 性能和 route planner 质量仍属于 `179` 的后续优化面，不在本轮修改范围内。

### 下一步

1. 在 native graph 下继续把 session resume 从 artifact-only 迁移到 checkpoint-first：优先按 `thread_id/session_id` 查 checkpoint，再落到 run artifact。
2. 用真实 stop-after-node partial run 验证 workbench 触发的 native resume，而不只是 CLI inspection。
3. 设计 SQLite checkpointer 的 state schema、artifact digest 引用和 UI 查询入口，逐步替换单目录 artifact resume。

## 2026-05-29 Phase 21：Workbench Resume 后半段恢复修复

### 问题

Phase 20 后继续做真实 `stop_after_node=verify_claims` partial run，并通过 workbench API 触发 native checkpoint resume。第一次真实恢复暴露了一个核心问题：

- Workbench job 返回 `completed`。
- `langgraph_node_checkpoints.json` 从 16 个节点推进到 19 个节点。
- 但 `post_gates/sec_benchmark_post_gates_summary.json` 没有生成。
- `langgraph_native_summary.json` 里的 `deterministic_gates_ok` 为空。

根因不是模型输出，也不是 artifact inspector，而是 `scripts/cloud/sec_agent_graph_runner.py --resume-native-checkpoint` 把 `--native-resume-include-synthesis` 同时用于控制 `synthesize_answer`、`verify_claims`、`run_deterministic_gates` 和 `render_answer`。当从 `verify_claims` 之后恢复并且 `include_synthesis=false` 时，graph 仍继续执行后半段节点，但 gates/render adapter 被置空，导致节点看似完成、真实 gates 产物缺失。

### 修复

- `scripts/cloud/sec_agent_graph_runner.py`
  - `--native-resume-include-synthesis` 只控制是否允许重跑 `synthesize_answer`。
  - `verify_claims`、`run_deterministic_gates`、`render_answer` 在 native resume 中始终接入真实 adapter。
  - 如果 checkpoint 的 `next_recoverable_node` 位于 `synthesize_answer` 或更早阶段，而用户没有显式允许 synthesis，CLI fail closed，返回 `synthesis_required_for_resume`，避免再次出现无声 no-op。

- `tests/test_sec_agent_graph_runner.py`
  - 新增边界测试：`build_judgment_plan`、`synthesize_answer`、`execute_second_pass_retrieval` 需要 synthesis；`verify_claims`、`run_deterministic_gates`、`render_answer` 不需要 synthesis。

### 验证

- 单测：
  - `pytest tests/test_sec_agent_graph_runner.py tests/test_sec_agent_langgraph_orchestrator.py tests/test_workbench_backend.py -q`
  - 结果：`47 passed`

- 编译：
  - `python -m py_compile scripts/cloud/sec_agent_graph_runner.py src/sec_agent/langgraph_orchestrator.py apps/workbench/backend/app.py`
  - 结果：通过

- 真实 partial run：
  - 输出目录：`.tmp_native_partial_verify_nvda_amd_20260529_resume_api_fixed`
  - 参数：`stop_after_node=verify_claims`，NVDA/AMD，FY2026，10-Q + 8-K + market snapshot，DeepSeek planner/synthesis，本地 CUDA BGE。
  - 结果：`status=stopped_after_node`，`latest_completed_node=verify_claims`，`next_recoverable_node=run_deterministic_gates`，coverage complete，claim verified。

- Workbench API resume：
  - 入口：`POST /api/native-checkpoints/resume`
  - 参数：`include_synthesis=false`
  - 结果：job `completed`，checkpoint count `16 -> 19`，latest node `persist_session_state`。
  - 修复后 `deterministic_gates` artifact 存在，digest 校验通过。
  - `langgraph_native_summary.json` 显示 `deterministic_gates_ok=True`，`rendered_answer_chars=2978`。

### 当前判断

- Workbench native checkpoint resume 已经能从 `verify_claims` 后恢复到 gates/render，并生成真实后处理 artifact。
- 这说明独立 `verify_claims` node、artifact checkpoint、workbench API resume 和 renderer 的后半段恢复边界已打通。
- 本轮同时暴露一个输出质量缺口：真实答案中仍出现过“是AMD的显著”“市盈率TTM为显著”这类不完整中文表达。当前 deterministic gates 能保证来源、数值和边界，但还没有覆盖中文表达完整性；后续应作为 memo quality gate / renderer QA 增强项处理，而不是用 resume 逻辑兜底。

### 下一步

1. 把 workbench session resume 的默认路径切到 checkpoint-first，并在 UI 上区分“可恢复”“已完成”“需要 synthesis 权限”三类状态。
2. 设计 memo language QA gate，专门捕获 dangling comparative、缺少比较对象、缺少数值单位等渲染质量问题。
3. 继续设计 SQLite checkpointer 的长期 session/thread 查询入口，减少单 run 目录 artifact resume 的耦合。
