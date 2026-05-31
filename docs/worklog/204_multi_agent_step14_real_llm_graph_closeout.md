# 204 Multi-agent Step 14 Real LLM Graph Closeout

日期：2026-05-30

## Prompt

用户要求继续按 185/186/188 设计补齐未完成的 multi-agent 部分，并直接使用临时 DeepSeek key 跑真实 LLM 测试。

## Decision

本轮把 185/186 中剩余的关键业务约束真正插入链路，而不是只停留在文档或 diagnostic parser：

- Universe / Relationship route 必须接入 graph，并通过 `relationship_graph_lookup` 或 sector-depth metadata 生成 bounded scope hypothesis。
- relationship evidence 只能生成研究范围和待验证假设，不能支持公司财务事实。
- Specialist、Memo Writer、Verifier 仍按 186 权限矩阵 fail-closed：specialist inspect-only，memo writer 无工具，verifier inspect-only 且不能覆盖 deterministic gate。
- Verifier repair loop 允许一轮 deterministic remove/downgrade repair，但必须保留原始违规审计信息。
- `industry_supply_chain_analyst` 只有在 industry / relationship scope 存在时才能激活，避免普通基本面/市场 memo 误触发。

## Work Completed

- 新增真实 relationship graph adapter 和 Universe LLM route：
  - `src/sec_agent/relationship_graph.py`
  - `src/sec_agent/universe_relationship_llm.py`
- MCP / registry / graph 接入：
  - `relationship_graph_lookup` 加入 MCP contract / registry。
  - `universe_relationship` agent 从 future tool 升级为可调用 bounded lookup。
  - `langgraph_orchestrator` 增加 `universe_relationship_expand` node，并把 relationship evidence requirements 合并进 EvidenceRequirementPlan。
- Specialist / Memo / Verifier 约束补齐：
  - `src/sec_agent/memo_llm.py` 增加 Memo Writer / Verifier LLM route。
  - `repair_multi_agent_memo_draft()` 支持一轮 deterministic repair 后重验。
  - Verifier repair 结果保留 `previous_errors`，renderer 对 blocked repair 输出 bounded answer。
- Research Lead real gate 修正：
  - `run_artifact` 成为合法 evidence route，并映射到 `coverage_reflection` / `run_inspect_artifacts`。
  - `retrieval_plan` 对 `run_artifact` 允许空 ticker/year，并强制 source tier 归一到 `run_artifact`。
  - Research Lead prompt 增加 compact output、run artifact route 和 industry/supply-chain 激活硬约束。
  - Research Lead LLM 默认 max tokens 从 1600 提到 2400，并对 `finish_reason=length` 返回更明确 repair diagnostic。
- 新增 / 更新测试：
  - relationship graph lookup / Universe LLM graph tests。
  - memo verifier repair loop tests。
  - industry/supply-chain scope gate test。
  - run_artifact evidence route / retrieval normalization test。

## Verification

- `pytest tests/test_multi_agent_universe_relationship_llm.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_judgment_memo_verifier.py -q`
  - `22 passed`
- Multi-agent / MCP / retrieval related regression:
  - `141 passed`
- 全量回归：
  - `pytest -q`
  - `358 passed in 11.38s`

## Real LLM Runs

均使用临时进程环境变量 `DEEPSEEK_API_KEY`，未写入 `.env`、文档、报告或 raw response。

- Research Lead activation + EvidenceRequirementPlan strict gate：
  - run id: `codex_full_research_lead_real_llm_after_step14_gate_pass`
  - result: `gate_status=pass`
  - cases: `5/5`
  - mode correct: `5/5`
  - validation: `5/5`
  - required agents: `5/5`
  - forbidden activation count: `0`
  - total latency: `125748 ms`
  - total tokens: `27228`
- Specialist memolet strict gate:
  - run id: `codex_specialist_memolet_real_llm_after_step14`
  - result: `gate_status=pass`
  - cases: `4/4`
  - evidence refs known: `4/4`
  - forbidden tool call count: `0`
  - total latency: `35329 ms`
  - total tokens: `7563`
- Universe Relationship + Memo Writer + Verifier smoke:
  - Universe validation: `pass`
  - Universe LLM call count: `1`
  - Memo route: `pass`
  - Verifier status: `pass`
  - Verifier error count: `0`

Full model-run ledger:

- `reports/model_runs/20260530_multi_agent_step14_deepseek_graph_closeout_v0_1.md`

## Safety Notes

- 未保存 API key、raw LLM response、工具原始 raw rows 或私有路径。
- `eval/sec_cases/outputs/...` 下新增的是 diagnostic output，按仓库规则默认不作为 tracking candidate。
- multi-agent graph 仍由 feature flag 控制；旧 native graph 未改成默认。

## Next Step

进入 Step 15/16：把完整 multi-agent graph 的 Workbench / CLI trace 产品化 gate 跑完，并做少量真实 graph smoke；仍保持 diagnostic-only，直到 source boundary、unsupported facts、预算和旧链路回归全部稳定。
