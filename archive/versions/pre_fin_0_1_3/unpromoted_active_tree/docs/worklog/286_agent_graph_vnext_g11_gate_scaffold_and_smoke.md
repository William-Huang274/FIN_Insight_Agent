# Agent Graph vNext G11 Gate Scaffold And Initial Smoke

## Problem

G1-G10 已经把 source-family、reflection、second pass、web boundary、playbook、shared context、fan-out/barrier 和 Milvus runtime switch 分别落地，但旧 full-chain eval 只能证明 6 月 1 日的基本链路，不能证明 vNext 的新合同：

- `graph_barriers` 是否进入 end-to-end score。
- `bounded_gap_register` 是否被视为 gap，而不是弱 proxy fallback。
- Milvus cloud/local/unavailable 是否显式进入 eval summary。
- Milvus semantic rows 是否不能支持 exact-value claim。
- Product / public source family 是否会进入标准 memo 的 specialist path。
- Research Lead 失败时是否能在 eval score 中保留可诊断原因。

## Decision

- 保留旧 `fin_agent_full_chain_multiturn_cases_v0_1.jsonl`，不破坏历史可比性。
- 新增 G11 专用 fixture：`tests/fixtures/fin_agent_vnext_g11_cases_v0_1.jsonl`。
- G11 fixture 先覆盖 12 个 case，覆盖 exact/focused/standard/deep/multi-turn，以及半导体、消费电子、SaaS、银行、能源、医药/医疗、汽车、零售。
- `eval_multi_agent_real_llm_chain.py` scoring 新增 vNext contract audit；不是用文字判断，而是检查 summary/result 的结构化字段。
- G11 总 checklist 暂不标完成；当前只完成 scaffold + 3-case smoke，完整 10-20 case gate 仍待跑。

## Work Completed

- `tests/fixtures/fin_agent_vnext_g11_cases_v0_1.jsonl`
  - 新增 12 个 vNext G11 cases。
  - 每个 case 均设置 `require_vnext_contract=true` 和 `require_milvus_runtime_contract=true`。
  - 覆盖 exact lookup、focused answer、standard memo、sector-depth、multi-turn。
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - 新增 `_vnext_contract_audit(...)`。
  - Scoring 检查 plan reflection、evidence fusion schema、source-boundary violation、bounded gap register、graph barrier、Milvus runtime contract、Milvus exact-authority misuse、private Milvus handle exposure、weak proxy fallback。
  - `_initial_state(...)` 为 G11 cases 注入 sanitized Milvus runtime inventory；本地无 URI/DB 时明确为 unavailable/not-bound。
  - Failed Research Lead route 的 validation errors / failure reason / routing trace 进入 case score。
- `src/sec_agent/langgraph_orchestrator.py`
  - Research Lead route status、failure reason、validation、rejected plan 进入 graph state 和 summary route diagnostics。
- `src/sec_agent/research_lead_llm.py`
  - 修复 LLM 把 schema hint 占位键 `agent_id` 原样写入 `model_policy_hint` / `agent_priorities` 后导致 validation fail 的问题。
  - 修复非 relationship focused/deterministic query 保留 `scope_mode=full_universe` 导致 fail 的问题；postprocess 收回到 `focused_peer`。
  - 保持 fail-closed：真正未知 agent/source、预算越界、错误 relationship expansion 仍失败。
- Tests
  - G11 fixture schema 覆盖面测试。
  - vNext scoring pass/fail 单测。
  - Research Lead placeholder policy map / focused scope drift normalization 单测。

## Initial Real Smoke

- `20260612_agent_graph_vnext_g11_exact_smoke_v0_1`
  - Case: `fin_g11_exact_msft_capex_zh`
  - Result: `1/1` pass
  - Tool calls: `1`
- `20260612_agent_graph_vnext_g11_focused_lly_smoke_v0_3`
  - Case: `fin_g11_focused_lly_product_cycle_zh`
  - Result: `1/1` pass
  - Tool calls: `6`
  - Root-cause repair before pass: Research Lead placeholder policy map + focused scope normalization.
- `20260612_agent_graph_vnext_g11_standard_nvda_amd_smoke_v0_1`
  - Case: `fin_g11_standard_nvda_amd_product_market_zh`
  - Result: `1/1` pass
  - Tool calls: `6`
  - Covered Product / Technology Specialist in a standard product/market memo path.

## Test Evidence

- `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py -q`
  - `20 passed`
- `python -m pytest tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_real_llm_chain_eval.py -q`
  - `43 passed`
- `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_specialist_llm.py -q`
  - `164 passed`
- `python -m compileall -q src scripts/cloud scripts/eval_multi_agent`
  - pass
- `git diff --check`
  - pass
- `python -m pytest -q`
  - `825 passed`

## Boundaries

- This is not the full G11 closeout.
- Local environment has `DEEPSEEK_API_KEY`, but no Milvus URI/DB binding; therefore current smoke validates local unavailable/not-bound behavior, not cloud Milvus query execution.
- G11 full gate still needs the full 12-case fixture run, including consumer electronics, SaaS, bank, energy, auto, retail, sector-depth, and multi-turn cases.

## Follow-Up

- Run full `fin_agent_vnext_g11_cases_v0_1.jsonl` 10-20 case gate.
- If cases fail, fix only root causes or expose bounded gaps; do not weaken source-boundary checks.
- If the user chooses cloud Milvus, rerun Milvus-enabled sector-depth cases with cloud runtime bound and keep exact-value misuse blocked.
