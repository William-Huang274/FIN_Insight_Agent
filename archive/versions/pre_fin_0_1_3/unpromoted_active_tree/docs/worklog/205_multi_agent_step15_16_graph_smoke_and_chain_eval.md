# 205 Multi-agent Step 15/16 Graph Smoke And Chain Eval

日期：2026-05-30

## Prompt

用户确认 Step 15/16 通过后，要求开始设计测试样例来测试 multi-agent 链路表现能力。

## Decision

本轮先把 Step 15/16 的真实 gate 补到稳定，再把链路能力测试落成可执行 deterministic eval，而不是只写样例说明。

关键判定：

- Step 16 真实 graph smoke 可以接受 bounded partial，但必须满足 `claim_verification=pass`、无 unsupported 泄漏、source boundary 不越界、预算可审计。
- `relationship_graph` 是合法业务 evidence route，但真实 lookup 由 Universe / Relationship graph node 执行，不作为普通 SEC/market operator route 执行。
- `tickers/search_scope_tickers` 只是查询范围，不等于真实 source inventory 可用 ticker；Universe validator 只用 `available_tickers`、`inventory_tickers`、`covered_tickers`、`universe_tickers` 或项目 inventory `companies` 判库存。
- Relationship-derived retrieval routes 必须在编译期按 activation total budget 和 agent registry per-agent `max_tool_calls` 裁剪，不能依赖 runtime ledger block 才停止。

## Work Completed

- Step 15 Workbench/profile gate：
  - `RuntimeProfile` 增加 `multi_agent_specialist_router`、`multi_agent_universe_router`、`multi_agent_memo_router`。
  - Workbench profile env now emits/parses `SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER`、`SEC_AGENT_MULTI_AGENT_UNIVERSE_ROUTER`、`SEC_AGENT_MULTI_AGENT_MEMO_ROUTER`。
- Step 16 graph correctness fixes：
  - LangGraph stop-aware edge now stops on terminal failed state, not only `stop_after_node`。
  - Added invalid activation plan stop test so fake completed state cannot continue into evidence operators / renderer。
  - Added `relationship_graph` route ownership mapping to Universe / Relationship。
  - Universe source inventory gate no longer treats query-scope tickers as available inventory。
  - Relationship evidence requirements are capped by activation route budget。
  - Retrieval plan routes are capped by agent permission matrix per-agent tool budgets before execution。
  - Memo Writer LLM output normalization now flattens nested `memo_draft` JSON so renderer receives `direct_answer`。
- Chain performance eval：
  - Added `tests/fixtures/multi_agent_chain_performance_cases_v0_1.jsonl` with 7 cases:
    - exact lookup
    - focused management commentary
    - standard peer / market memo
    - deep AI capex relationship scope
    - run artifact inspection
    - unsupported specialist block
    - verifier repair loop
  - Added `scripts/eval_multi_agent_chain_performance.py` deterministic scorer.
  - Added `tests/test_multi_agent_chain_performance_eval.py`.

## Verification

- Step 15 targeted gate:
  - `pytest tests/test_workbench_artifacts.py tests/test_workbench_profiles.py tests/test_multi_agent_langgraph_routing.py -q`
  - `15 passed`
- Relationship / memo / graph targeted gate after fixes:
  - `pytest tests/test_multi_agent_chain_performance_eval.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_universe_relationship_llm.py tests/test_multi_agent_langgraph_routing.py -q`
  - `37 passed`
- Chain performance deterministic eval:
  - `python scripts/eval_multi_agent_chain_performance.py --output-dir reports/eval/multi_agent_chain_performance/codex_v0_3 --fail-on-gate`
  - `7/7 passed`, `pass_rate=1.0`
- Full regression:
  - `pytest -q`
  - `366 passed in 11.85s`

## Real LLM Step 16

均使用临时进程环境变量 `DEEPSEEK_API_KEY`，未写入 `.env`、文档、报告或 raw response。

- Full Step 16 graph smoke v0.3：
  - output: `eval/sec_cases/outputs/multi_agent_graph_smoke/codex_step16_real_llm_graph_smoke_v0_3/step16_graph_smoke_summary.json`
  - cases: `3`
  - passed: `3`
  - focused: `focused_answer`, `claim_verification=pass`, `tool_call_count=3`
  - standard: `standard_memo`, bounded by specialist verification, no unsupported leakage, `tool_call_count=3`
  - deep: `deep_research`, Universe validation `pass`, bounded by specialist verification, `tool_call_count=11`
- Post per-agent budget fix deep probe v0.4：
  - output: `eval/sec_cases/outputs/multi_agent_graph_smoke/codex_step16_deep_budget_probe_v0_4/step16_deep_budget_probe.json`
  - `gate_status=pass`
  - `loop_break_reason=""`
  - `tool_call_count=11`
  - `route_count=10`
  - `route_budget_pruning.dropped_route_count=1`

## Safety Notes

- 未保存 API key、raw LLM response、私有路径或 raw evidence 全文。
- `eval/sec_cases/outputs/...` 和 `reports/eval/...` 是 diagnostic/generated outputs，不作为默认 tracking candidate。
- Multi-agent graph 仍由 feature flags 控制；旧 native graph 未改成默认。

## Next Step

- 把 deterministic chain performance eval 接入后续 release/Workbench smoke 命令。
- 为真实 LLM graph smoke 增加一个小型可重复 runner，避免后续继续用 inline probe。
- 后续若要推进生产化，先补真实 evidence rows 下的 specialist 质量样例，而不是只看 dry-run bounded rows。
