# 199 Multi-agent 185/186 Replan And Step 9 Data-view Gate

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：188 Step 8+ 已按 185/186 重新对齐；Step 9 deterministic gate 已落地
关联文档：`185_multi_agent_investment_research_framework_draft.md`、`186_multi_agent_tool_data_access_matrix_draft.md`、`188_multi_agent_architecture_execution_plan.md`、`198_multi_agent_step8_skill_backfill_and_specialist_llm_route.md`

## 问题

用户指出 188 早先对 185/186 的 multi-agent 细节消化不足，尤其是：

- 185 的 Role-specific Skill 拆分。
- 186 的 agent 权限矩阵落地。
- 工具和数据源归属、data-view 边界、source family claim scope。

复核后确认：multi-agent 不能只推进 LLM route 或 graph stub；必须先把业务角色、权限、证据需求和可见数据视图做成可测试合同。

## 对齐决策

- Research Lead / Universe / Reflection 只提出 business-level evidence requirements，不能选择物理 BM25、DuckDB、index path 或 raw source。
- Deterministic compiler 负责把 EvidenceRequirementPlan 编译成 retrieval routes / MCP tool calls。
- 每个 agent 的数据输入必须由 registry `allowed_data_views` 裁剪，不能由节点随意传完整 graph state。
- Industry / Supply Chain Analyst 是 185/186 的正式 specialist，不应继续缺席；它只能消费 industry / relationship bounded summaries，不能用关系图或行业数据支持公司披露财务数值。
- Memo Writer 只消费 verified summary / judgment plan，不消费 raw context rows。

## 已完成

文档：

- 更新 `188_multi_agent_architecture_execution_plan.md` Step 8+：
  - 明确 `industry_supply_chain_analyst` 已进入 registry / skill / contract。
  - Step 9 增加当前实现状态：EvidenceRequirementPlan enrichment、operator owner/source family validation、data-view builder。
  - Step 12 从 3-case specialist fixture 修正为 4-case，并把 Industry/Supply-Chain 状态改为已接入 bounded diagnostic。
- 更新 `198_multi_agent_step8_skill_backfill_and_specialist_llm_route.md`：
  - 补充 Industry/Supply-Chain skill 和 4-case bounded fixture 状态。
- 更新 `00_internal_master_checklist.md`。

代码：

- `src/sec_agent/multi_agent_runtime.py`
  - 新增 `build_multi_agent_evidence_requirement_plan()`。
  - 新增 `validate_multi_agent_evidence_requirement_plan()`。
  - 新增 `build_agent_data_view()`。
  - EvidenceRequirementPlan 现在补充 `source_families`、`operator_owners`、`claim_families`、`route_intents`、`planner_boundary`。
  - Data-view builder 按 `agent_registry.allowed_data_views` 输出 summary、artifact refs、bounded rows、coverage summary、tool trace summary、relationship summary 或 verified summary，并剥离 raw text、物理路径和 private data marker。
- `src/sec_agent/langgraph_orchestrator.py`
  - `compile_evidence_requirements` 节点现在写入 `evidence_requirement_plan`。
  - Multi-agent summary / checkpoint summary 增加 evidence requirement count 和 validation status。
- `src/sec_agent/specialist_llm.py`
  - Specialist request 改为优先从 `build_agent_data_view()` 获取 bounded rows。
- `tests/test_multi_agent_evidence_requirements.py`
  - 新增 Step 9 deterministic fixture gate。

## 验证

已通过：

```text
pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_langgraph_routing.py -q
27 passed

python -m compileall -q src/sec_agent/multi_agent_runtime.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/specialist_llm.py
```

## 安全说明

- 未写入 API key、token、SSH 密码或私有凭据。
- 文档和 fixture 不包含真实 secret。
- Agent data view 不暴露 raw evidence 全文、private data path、index path 或 local filesystem path。

## 后续状态

本记录之后已继续完成 Step 10 的 schema / validator / diagnostic flag 接入，详见 `200_multi_agent_step10_research_lead_evidence_requirements.md`。

下一步应进入 Step 11：把 Coverage / Reflection 的 second-pass request 与 EvidenceRequirementPlan requirement id、source family gap 和 tool ledger summary 绑定。
