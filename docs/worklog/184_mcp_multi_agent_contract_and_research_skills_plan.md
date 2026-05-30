# 184 MCP / Multi-agent Tool Contract and Research Skill Plan

Date: 2026-05-30

## 背景

当前 full238 已经把 SEC 10-K/10-Q、8-K 业绩新闻稿、市场快照和行业数据源推进到同一个研究链路里。数据范围变大以后，单个 agent 同时承担 planner、检索、证据充足性判断、验证和写作会出现三个问题：

1. 角色冲突：同一个模型既写结论又检查自己，容易漏掉证据缺口。
2. 上下文压力：SEC、market、industry、run artifact 全部塞进一个 prompt，会放大 token 成本和遗漏风险。
3. 工具边界分散：CLI、Workbench、LangGraph 节点和未来 MCP client 如果各自调用不同脚本，后续很难维护。

因此下一步不是先堆一个“多 agent demo”，而是先把工具合同、研究 skill 和图编排状态稳定下来。MCP 只是标准化工具边界的承载方式之一；核心是让 SEC / market / industry / run artifact 这些能力能被不同 agent 和入口复用。

## 目标

本阶段先做三件事：

1. 建立 MCP-facing 工具合同，让 SEC、market、industry、run artifact 工具的输入、输出、来源边界和 handler 归属统一。
2. 把 A/B 阶段定义的投研方法压缩成可注入模型的 research skill，而不是把长文档直接塞进 prompt。
3. 为后续 multi-agent / A2A 编排留出清晰角色边界：Research Planner、Evidence Operator、Coverage / Reflection、Verifier、Memo Writer。

本阶段不做的事：

1. 不直接把所有旧脚本重写成 MCP server。
2. 不让 MCP 绕过 LangGraph / coverage / gates。
3. 不把行业数据、市场数据或 run artifact 文本当作新的无限制证据源。

## 角色划分

| 角色 | 责任 | 主要工具 |
| --- | --- | --- |
| Research Planner | 理解用户问题，生成 Query Contract 和 EvidenceRequirementPlan | research skill、inventory、relationship graph |
| Evidence Operator | 执行 SEC/market/industry 检索和结构化取数 | `sec_search_filings`、`sec_query_exact_value_ledger`、`market_get_snapshot`、`industry_get_snapshot` |
| Coverage / Reflection | 判断证据是否足够，是否触发二次检索 | coverage matrix、source gaps、run artifacts |
| Verifier | 校验数值、来源层级、期间口径、市场日期和 unsupported claims | ledger、coverage、post gates、run artifacts |
| Memo Writer | 只在证据和判断计划约束内写投研 memo | synthesis prompt、research skill、verified judgment plan |

规则的职责不是替模型判断“应该研究什么”，而是校验节点输出是否可执行、是否越过证据边界、是否需要降级或二次检索。

## MCP 工具合同 v0.1

代码源：

```text
src/sec_agent/mcp_contracts.py
scripts/mcp/export_sec_agent_mcp_contracts.py
configs/mcp/sec_agent_mcp_tool_contracts_v0_1.json
```

当前先定义 6 个 MCP-facing 工具合同：

| 工具 | 来源层级 | 作用 |
| --- | --- | --- |
| `sec_search_filings` | `primary_sec_filing`、`company_authored_unaudited_sec_filing` | 在显式公司/年份/披露文件/source tier 范围内检索 SEC 文本和结构化对象 |
| `sec_query_exact_value_ledger` | `primary_sec_filing` | 按 ticker、fiscal year、form type、metric family、period role 查询可比财务值 |
| `market_get_snapshot` | `market_snapshot` | 获取非实时市场快照、收益、相对收益、回撤、估值和事件窗口证据 |
| `industry_get_snapshot` | `industry_snapshot` | 获取行业 source-family evidence 或 observation，用于宏观/行业背景解释 |
| `run_inspect_artifacts` | `run_artifact` | 检查保存 run 的 state、coverage、ledger、gates、checkpoint、性能和渲染答案 |
| `run_read_artifact` | `run_artifact` | 有边界读取单个 run artifact，用于审计、resume 和 UI 检查 |

合同要求：

- 工具名使用 MCP-safe snake_case。
- 输入输出都使用 JSON schema。
- 每个工具必须声明 `source_boundaries.allowed_claim_types` 和 `source_boundaries.prohibited_claims`。
- 每个工具必须声明 handler 归属，但 handler 可以先指向现有 Python adapter；后续 MCP server 再包装同一 handler。
- 工具不得暴露 API key、私有路径以外的无界内容或未裁剪的大型 artifact。

## Research Skill v0.1

Skill 文件：

```text
src/sec_agent/prompts/skills/investment_research_workflow_skill_v0_1.md
src/sec_agent/prompts/skills/evidence_requirement_and_sufficiency_skill_v0_1.md
src/sec_agent/research_skills.py
```

Skill 不替代工具，也不替代 eval。它只告诉模型如何把投研问题转成研究工作流：

- 识别 fundamental change、peer comparison、supply-chain validation、market reaction、valuation context、industry context、risk/counterevidence。
- 区分 SEC、8-K、market snapshot、industry snapshot、relationship graph 的证据权重和边界。
- 让 planner 输出 EvidenceRequirementPlan，而不是直接回答。
- 让 reflection 在证据不足且现有 source 可查时触发二次检索。
- 让 synthesis 按投研 memo 结构输出，并在证据不足时降级结论。

当前已先把 planner prompt 接入 `research_skill_prompt("planner")` 的压缩版。后续再把 reflection 和 synthesis 分别接入对应 skill，避免一次性改动 synthesis 长 prompt 造成回归难定位。

## 执行步骤

### Step 1：工具合同源稳定

- 新增 `src/sec_agent/mcp_contracts.py`。
- 新增导出脚本 `scripts/mcp/export_sec_agent_mcp_contracts.py`。
- 导出 `configs/mcp/sec_agent_mcp_tool_contracts_v0_1.json`。
- 单测校验工具名、schema、source boundary 和 handler 字段。

### Step 2：投研 skill 注入

- 新增 research skill markdown。
- 新增 `src/sec_agent/research_skills.py` loader。
- planner prompt 注入压缩版 skill。
- 单测校验 skill 可加载、角色映射正确、planner prompt 包含 skill 关键约束。

### Step 3：MCP runtime 过渡层

- 先实现不依赖 MCP SDK 的 bounded artifact reader，解决 run artifact 工具的安全读取边界。
- 后续增加真实 MCP server 时，直接从 `mcp_contracts.py` 注册工具，不再重新定义 schema。

### Step 4：工具执行标准化

- SEC 检索继续复用 LangGraph adapter，但工具输出要向合同字段对齐。
- Market / industry route 从 evidence row 注入逐步扩展到 DuckDB observation 查询工具。
- Run artifact 工具必须保留 max bytes、digest、artifact id 和 path escape 防护。

### Step 5：Multi-agent / A2A 编排

- 在 LangGraph 中把 Research Planner、Evidence Operator、Reflection、Verifier、Memo Writer 拆成可检查节点。
- Reflection 节点负责发起二次检索，不把可查证据作为“建议补查”丢给用户。
- Verifier 节点只校验 claim，不参与写作。
- Memo Writer 只消费 verified judgment plan、ledger、coverage 和 evidence rows。

## 验收标准

当前阶段验收：

- MCP 工具合同可导出、可校验。
- Research skill 可加载，并已经进入 planner prompt。
- run artifact bounded reader 能防止 path escape 和无界读取。
- 不需要 MCP SDK 也能完成合同级单测。

下一阶段验收：

- 本地 MCP server smoke 能通过一个 client 调用 `sec_query_exact_value_ledger`、`industry_get_snapshot`、`run_inspect_artifacts`。
- 一个真实 full-chain case 能在 LangGraph trace 中看到 planner skill、工具调用、coverage reflection、二次检索或降级决策。
- Workbench 使用同一套工具 registry，不再维护另一套“UI 专用”工具逻辑。

## 2026-05-30 MCP runtime wrapper 与 industry DuckDB 查询

### 本轮目标

在 MCP server 正式接入前，先做一层可测试的本地 runtime registry，避免 MCP 工具只停留在 JSON 合同。同时把 `industry_get_snapshot` 从 evidence row 注入推进到 DuckDB observation 级查询。

### 已完成

- 新增 `src/sec_agent/industry_snapshot.py`：
  - `query_industry_snapshot(...)` 支持查询 `industry_snapshot.duckdb`。
  - 支持按 `source_family`、`provider`、`dataset_id`、`series_id`、日期区间和 `facet` 过滤。
  - 支持 `latest_only=true`，按 source family / dataset / series 返回最新 observation。
  - 如果 DuckDB 不存在但提供 `industry_evidence_rows.jsonl`，可回退读取 evidence row；这不是业务兜底，而是同一 source-family 的降级读取方式。
- 新增 `src/sec_agent/mcp_tool_registry.py`：
  - 暴露 `invoke_mcp_tool(tool_name, arguments)`。
  - 当前已绑定 `sec_search_filings`、`sec_query_exact_value_ledger`、`market_get_snapshot`、`industry_get_snapshot`、`run_inspect_artifacts`、`run_read_artifact`。
  - `sec_search_filings` 不另写旁路检索，而是加载现有 `sec_agent_interactive.py` 的 `build_query_plan_for_graph` 和 `retrieve_context_for_graph`，把 MCP tool call 中的 evidence requirement 写回 Query Contract 后交给 LangGraph retrieval adapter 执行。
- 新增 `src/sec_agent/mcp_server.py`：
  - 使用可选 MCP SDK。当前本地环境尚未安装 `mcp` 包，因此 server wrapper 先保持 SDK-optional。
  - 安装 `mcp>=1.9.0` 后，可通过 `scripts/mcp/run_sec_agent_mcp_server.py` 启动 stdio server。
  - 工具函数使用明确参数签名，而不是单个 `arguments` blob，方便 MCP client 自动生成可调用 schema。
- 新增 `scripts/mcp/invoke_sec_agent_mcp_tool.py`：
  - 不依赖 MCP client，可直接调用 registry 做本地 smoke。
  - 用于 CI / 本地快速验证工具合同和 runtime handler 是否一致。
- 新增 `scripts/mcp/smoke_sec_agent_mcp_stdio.py`：
  - 使用 `mcp.client.stdio` 启动本仓库 MCP server。
  - 验证 `list_tools`，可选调用 `list_sec_agent_tools`。
  - 用作后续 CI / 本地 / 云端 MCP server smoke 入口。
- `requirements.txt` 新增 `mcp>=1.9.0`，本地当前已安装 `mcp==1.27.2`。
- `configs/mcp/sec_agent_mcp_tool_contracts_v0_1.json` 已重新导出：
  - `sec_search_filings` 输出 schema 增加 `query_contract`、`selected_tickers`、`selected_years`、`context_runtime` 和 `row_count`。
  - `industry_get_snapshot` handler 指向 `sec_agent.industry_snapshot.query_industry_snapshot`。

## 2026-05-30 sec_search_filings registry 绑定

### 本轮目标

把 SEC 检索工具从合同层推进到可调用 registry，但保持主链路边界：工具调用必须走现有 planner / retrieval plan / BM25 / ObjectBM25 / BGE / context artifact 入口，不能另写一条更快但绕过 coverage 的简化检索。

### 已完成

- `src/sec_agent/mcp_tool_registry.py` 新增 `sec_search_filings` handler。
- handler 会构造交互链路需要的 args，包括 manifest、BM25/ObjectBM25 index、ledger store、BGE 参数、context runner 和 planner 参数。
- handler 先调用 `build_query_plan_for_graph` 生成基础 Query Contract，再把 MCP 参数中的 `tickers`、`years`、`filing_types`、`source_tiers`、`metric_families`、`period_roles`、`retrieval_route`、`candidate_budget`、`rerank_budget` 编译成 `evidence_requirements`。
- handler 再调用 `retrieve_context_for_graph`，返回：
  - `context_rows`
  - `query_contract`
  - `retrieval_trace`
  - `context_runtime`
  - `candidate_counts`
  - `artifact_refs`
  - `source_gaps`
- `sec_search_filings` 会拒绝非 SEC source tier，例如 `market_snapshot` 和 `industry_snapshot`，这些必须走对应 MCP tool。
- 未显式传入 `output_dir` 时，handler 会按 query digest 生成唯一 `eval/sec_cases/outputs/mcp_sec_search/<run>` 目录，避免多次 MCP 调用互相覆盖。
- `src/sec_agent/mcp_server.py` 增加 `sec_search_filings(...)` 显式参数签名，方便后续 MCP client 和 multi-agent 编排直接调用。
- `tests/test_sec_agent_mcp_runtime_tools.py` 新增 mock adapter 单测，确认该工具调用现有 graph adapter，并确认 evidence requirement 会进入 Query Contract。

### 本地验证

- py_compile：
  - `src/sec_agent/industry_snapshot.py`
  - `src/sec_agent/mcp_tool_registry.py`
  - `src/sec_agent/mcp_server.py`
  - `src/sec_agent/mcp_contracts.py`
  - `src/sec_agent/mcp_runtime.py`
  - `scripts/mcp/*.py`
- 单测：
  - `pytest tests/test_sec_agent_mcp_contracts.py tests/test_sec_agent_mcp_runtime_tools.py -q` -> `9 passed`
  - `pytest tests/test_sec_agent_mcp_contracts.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_sec_agent_industry_snapshot_route.py tests/test_sec_agent_retrieval_plan.py -q` -> `29 passed`
- 合同校验：
  - `python scripts/mcp/export_sec_agent_mcp_contracts.py --check` -> `tool_count=6`
- Registry smoke：
  - `python scripts/mcp/invoke_sec_agent_mcp_tool.py --list-tools --tool sec_search_filings` 能列出 `sec_search_filings`。
- MCP SDK smoke：
  - `create_mcp_server()` 可创建 `FastMCP` server 对象。
  - `python scripts/mcp/smoke_sec_agent_mcp_stdio.py --call-contract-tool` 通过。
  - stdio client 的 `list_tools` 返回 7 个工具，包含 `sec_search_filings`。
  - 同一 client 调用 `list_sec_agent_tools` 成功返回合同内容。
- 真实本地 DuckDB smoke：
  - tool: `industry_get_snapshot`
  - db: `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales/industry_snapshot.duckdb`
  - args: `source_families=["industry_utilities_power_demand"]`、`providers=["EIA"]`、`facets={"sectorid":"ALL"}`、`latest_only=true`
  - result: `status=ok`，返回 1 条 EIA retail-sales evidence row 和 1 条最新 US all-sector observation。

### 当前边界

- `sec_search_filings` 已进入 registry，但真实大范围调用仍取决于本地/云端是否有对应 manifest、BM25/ObjectBM25 index、BGE 模型和 ledger store。
- 当前已补充一个中小范围真实 SEC 检索 smoke，确认 full30 manifest/index/BGE 路径能返回完整 telemetry；full238/full-source 仍需要在准备好运行环境后跑一次真实 smoke。
- MCP SDK 已安装；server wrapper 和 stdio client smoke 已通过。尚未用 MCP client 调真实 SEC 检索，因为这会进入 manifest/index/BGE 路径，需要准备对应数据环境。
- Market tool 当前读取 evidence row JSONL，尚未接 DuckDB catalog；后续可以按 market snapshot catalog 做 observation/analytics 级查询。

### 下一步

1. 把 market snapshot tool 从 JSONL evidence row 扩展到 DuckDB catalog 查询。
2. 让 Workbench 后端优先调用 `mcp_tool_registry`，避免 UI 和 CLI 各维护一套工具入口。
3. 在 full238/full-source 环境上重复真实 SEC reranker smoke，确认大范围 scope 下 telemetry 和 source contract 仍稳定。

## 2026-05-30 本地真实 SEC reranker 路径 smoke

### 目标

用本地 full30 mixed-with-8K 真实 manifest、BM25/ObjectBM25 index 和本地 BGE CrossEncoder 跑一个中小 SEC 检索 case，确认 `sec_search_filings` 在真实 index+BGE 路径下不是只通过 mock adapter，而是能返回完整的 `context_rows`、`retrieval_trace` 和 `candidate_counts`。

### 诊断 run：混合 form/year cross-product 被 source contract 拦截

- run: `eval/sec_cases/outputs/mcp_sec_search/local_nvda_amd_smoke_20260530/mcp_sec_search_result.json`
- scope: `tickers=["NVDA","AMD"]`、`years=[2025,2026]`、`filing_types=["10-K","8-K"]`
- result: `status=partial`、`row_count=0`
- root cause:
  - source resolver 找到 `NVDA 2025 10-K`、`NVDA 2026 8-K`、`AMD 2025 10-K`、`AMD 2026 8-K`。
  - 但该请求被编译成 `(ticker, year, filing_type)` cross-product，因此同时要求 `2025 8-K` 和 `2026 10-K`，这些 filing 在当前 artifact scope 中不存在。
  - 链路按 source contract 正确停止，没有进入 retrieval；这不是 BGE 或索引问题。

后续 mixed 10-K + 8-K MCP 调用应由 planner/executor 编译为可用 `(ticker, year, form)` tuple，或拆成 route-specific tool calls，例如 FY2025 `10-K/primary_sec_filing/filing_text` 与 FY2026 `8-K/company_authored_unaudited_sec_filing/8k_commentary`，不能把不同 form 的可用年份强行做笛卡尔积。

### 通过 run：FY2025 10-K 真实 BGE reranker 路径

- result: `eval/sec_cases/outputs/mcp_sec_search/local_nvda_amd_10k_smoke_20260530/mcp_sec_search_result.json`
- run dir: `eval/sec_cases/outputs/mcp_sec_search/local_nvda_amd_10k_smoke_20260530/run`
- scope:
  - `tickers=["NVDA","AMD"]`
  - `years=[2025]`
  - `filing_types=["10-K"]`
  - `source_tiers=["primary_sec_filing"]`
  - `retrieval_route="filing_text"`
  - `metric_families=["data_center_revenue","revenue"]`
  - `period_roles=["ANNUAL"]`
- local reranker:
  - model: `D:/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/snapshots/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`
  - device: `cuda`
- result:
  - `status=ok`
  - `row_count=8`
  - row distribution: `AMD=4`、`NVDA=4`
  - form/source: all rows are `FY2025 10-K` + `primary_sec_filing`
  - source gaps: `[]`
- candidate telemetry:
  - `candidate_row_count_pre_rerank=8`
  - `candidate_sent_to_bge=8`
  - `route_candidate_stats[0].retrieval_route=filing_text`
  - `candidate_budget=40`
  - `rerank_budget=12`
  - `candidate_count=8`
  - `rerank_eligible_count=8`
  - `timing_ms.candidate_generation=7`
  - `timing_ms.context_rerank=1704`
- runtime:
  - `context_runner=in_process`
  - `context_cache_hit=false`
  - `context_resource_load_ms=49453`
  - `elapsed_ms=51351`

结论：`sec_search_filings` 的真实 reranker 路径已返回完整字段，且 trace 中可见 `candidate_generators=["evidence_bm25","object_bm25","requirement_bm25"]`、`final_selector="bge-reranker-v2-m3"`、`retrieval_plan_enabled=true`、route-level candidate stats、coverage reservation 和 BGE 模型路径。当前耗时主要来自每次进程冷启动加载 CrossEncoder 权重，实际候选生成和 rerank 本身在本 case 中分别约 7ms 和 1.7s。

## 2026-05-30 mixed 10-K/8-K MCP route scope 修复

### 修改

- `sec_search_filings` 在收到混合 SEC 表单请求时，不再把顶层 `years x filing_types` 展开成不可用的笛卡尔积。
- handler 会读取当前 manifest，把可用 filing 编译成 route-specific requirements：
  - 10-K / 10-Q / 20-F / 40-F -> `filing_text`
  - 8-K -> `8k_commentary`
  - 6-K -> 暂按公司发布材料 source tier 记录，后续进入 foreign issuer route 时再细分。
- 对于用户请求范围内不存在的 `(ticker, year, form_type, source_tier)`，写入 `query_contract.source_coverage_gaps`，并同步返回到 MCP result 顶层 `source_gaps`。这样即使 retrieval 返回了 rows，上层 agent / UI 仍能看见缺口。
- benchmark source resolver 已改为优先读取 `retrieval_plan` 中的 route scope，而不是仅用顶层 `companies x years x filing_types` 判断 source completeness。

### 单测

- `pytest tests/test_sec_agent_mcp_runtime_tools.py tests/test_sec_benchmark_eval_mixed_context.py tests/test_sec_agent_retrieval_plan.py -q`
- result: `26 passed`

覆盖点：

- MCP registry 会把 FY2025 10-K 和 FY2026 8-K 拆成两条可用 route requirement。
- `source_gaps` 会保留 contract 中的缺口，不会因为已返回 context rows 而被吞掉。
- benchmark source resolver 会使用 retrieval plan 的 route scope 判断 source completeness。

### 真实本地 mixed smoke

- result: `eval/sec_cases/outputs/mcp_sec_search/local_nvda_amd_mixed_10k8k_smoke_20260530_r2/mcp_sec_search_result.json`
- scope:
  - `tickers=["NVDA","AMD"]`
  - `years=[2025,2026]`
  - `filing_types=["10-K","8-K"]`
  - `source_tiers=["primary_sec_filing","company_authored_unaudited_sec_filing"]`
  - no explicit `retrieval_route`
- result:
  - `status=ok`
  - `row_count=12`
  - rows include both `10-K` and `8-K`
  - rows include both `filing_text` and `8k_commentary`
  - rows include both `AMD` and `NVDA`
  - `source_gap_count=4`
  - `query_contract_gap_count=4`
- candidate telemetry:
  - `candidate_row_count_pre_rerank=16`
  - `candidate_sent_to_bge=16`
  - route 1: `mcp_sec_search_10_k_2025::filing_text`，`candidate_count=8`，`rerank_eligible_count=8`
  - route 2: `mcp_sec_search_8_k_2026::8k_commentary`，`candidate_count=8`，`rerank_eligible_count=8`
  - `timing_ms.candidate_generation=9`
  - `timing_ms.context_rerank=2580`

结论：MCP SEC 检索已经能在真实 index+BGE 路径下处理“FY2025 10-K + FY2026 8-K”这种混合来源请求。当前缺口不是检索失败，而是 contract 明确告知 `2025 8-K`、`2026 10-K` 等 cross-product 项不在当前 artifact 范围内；实际可用 route 仍然进入 retrieval 并返回证据。
