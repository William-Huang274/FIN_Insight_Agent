# 198 Multi-agent Step 8 Skill Backfill And Specialist LLM Route

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：Step 8 代码补齐；Specialist Analyst 真实 LLM 诊断接入口已接入，真实 DeepSeek strict run 待环境 key
关联文档：`188_multi_agent_architecture_execution_plan.md`、`196_multi_agent_specialist_llm_parser_gate.md`、`197_multi_agent_188_design_digest_correction.md`

## 问题

用户要求回头把 Step 8 补好，再继续接入真实 LLM。复查后确认：

- `agent_registry.py` 已声明 `fundamental_analysis`、`market_valuation_analysis`、`risk_counterevidence`、`relationship_universe`、`evidence_operator_tool_use`、`judgment_plan_aggregation`、`renderer` 等 skill id。
- 但 `research_skills.py` 之前不能加载这些 skill id，对应 prompt 文件也不存在。
- `specialist_llm.py` 仍使用内联短 role instruction，没有真正注入正式 role-specific skill prompt。

这会导致 188 的 `185/186 Digest Gate` 只在文档层成立，未完全落到代码。

## 已完成

Step 8 补齐：

- 新增 Specialist / Universe / Operator / Aggregator / Renderer role-specific skill prompt：
  - `fundamental_analysis_skill_v0_1.md`
  - `industry_supply_chain_analysis_skill_v0_1.md`
  - `market_valuation_analysis_skill_v0_1.md`
  - `risk_counterevidence_skill_v0_1.md`
  - `relationship_universe_skill_v0_1.md`
  - `evidence_operator_tool_use_skill_v0_1.md`
  - `judgment_plan_aggregation_skill_v0_1.md`
  - `renderer_skill_v0_1.md`
- 更新 `research_skills.py`，使所有 registry skill id 都能加载，并给每个 agent id 配置 shared boundary + role skill。
- 更新 `agent_registry.py`，registry validator 现在会 fail closed unknown skill id。
- 更新 Specialist LLM prompt 注入，`specialist_llm.py` 改为通过 `research_skill_prompt(agent_id)` 注入正式 skill，不再依赖内联短说明。

真实 Specialist LLM 诊断接入口：

- 新增 `specialist_llm_config_from_env()` 和 `route_specialists_from_env()`。
- `build_multi_agent_orchestration_graph_from_env()` 现在读取 `SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER`：
  - `mock` / `off` / 空值：保持默认 stub/mock。
  - `llm` / `deepseek` / `api`：调用真实 Specialist LLM route。
- 新增 `build_specialist_request_from_state()`，从 graph state 裁剪 bounded rows，不暴露 raw paths/private fields。
- LLM route 失败时生成 blocked memolet，后续 specialist verification 会在 Memo Writer 前 fail closed。

Step 12 诊断资产：

- 新增 bounded fixture：`tests/fixtures/multi_agent_specialist_memolet_cases_v0_1.jsonl`
  - Fundamental：SEC ledger / filing summary。
  - Industry / Supply Chain：industry snapshot + relationship graph summary。
  - Market-Valuation：market snapshot summary，含 `snapshot_id` 和 `as_of_date`。
  - Risk-Counterevidence：缺 AWS backlog 支撑的 unsupported/conflict case。
- 新增脚本：`scripts/eval_multi_agent_specialist_memolet.py`
  - 调真实 Specialist LLM。
  - 保存 memolet、validation、routing trace、token/latency summary。
  - 不保存 raw LLM response 和 API key。
  - strict gate 要求 4/4 schema pass、known evidence refs、direct tool call 0、expected unsupported/conflict 命中。

## 验证

已通过：

```text
pytest tests/test_research_skills.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_specialist_llm.py -q
16 passed

pytest tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_langgraph_routing.py -q
15 passed

pytest tests/test_research_skills.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_contracts.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_specialist_llm.py -q
36 passed

python -m compileall -q scripts src
pytest -q
316 passed
```

附带修复：

- 全量测试暴露 `scripts/cloud/sec_agent_interactive.py` 中 `_write_run_data_fingerprint()` 对旧 `args` 缺 `industry_evidence_path` 不兼容，已改为 `getattr()`，对应单测通过。

## 真实 LLM 状态

当前 shell 中 `DEEPSEEK_API_KEY` 不存在，因此未执行 4-case real DeepSeek strict run。已运行不带 strict 的单 case smoke，结果按预期 fail closed：

- `gate_status=fail`
- `failure_reason=provider_error: deepseek backend requires API key env var`
- `forbidden_tool_call_count=0`
- 无 deterministic fallback

下一步在环境变量设置后执行：

```text
python scripts/eval_multi_agent_specialist_memolet.py --strict
```

通过后再记录 `reports/model_runs/<run_id>.md`，并更新 model run index。

## 安全说明

- 未写入 API key、token、密码或私有凭据。
- 真实诊断输出合同不保存 raw LLM response。
- Specialist graph route 只使用 bounded rows / summary / refs，不暴露 raw evidence 全文或私有路径。
