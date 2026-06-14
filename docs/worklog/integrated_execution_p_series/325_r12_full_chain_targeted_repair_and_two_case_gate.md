# R12 Full-Chain Targeted Repair And Two-Case Gate

## Problem Or Prompt

用户要求继续推进 R12 vNext case catalog 落地测试，并明确要求：测试遇到问题不能用 fallback 藏住，必须先定位和修复，再复测。

本轮从 Workbench 后端真实 full-chain 入口跑两个新 catalog case：

- `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025`
- `fin_deep_cloud_capex_msft_amzn_googl_supplier_026`

首轮 run `r12_successor_new_cases_20260614` 失败，Workbench summary 显示 `case_count=2`、`pass_count=0`、`failed_cases=2`。

## Root Cause

失败不是 memo writer 表达层问题，也不是 Milvus runtime contract 问题。两个 case 都完成了检索、run audit、dimension memo、vNext contract、memo/verifier 等主体流程，失败集中在 specialist real evidence quality。

1. Cloud capex case 缺 `risk_counterevidence_analyst`
   - R12 deep research 合同要求六维分析和 risk/counterevidence 专员。
   - deterministic router 的 fixture 方向已经把 deep research 下 risk 视为 supporting，但 Research Lead 归一化仍只在显式风险词出现时保留 risk。
   - 结果：case 需要 risk，实际 activation plan 未激活 risk，gate 正确失败。

2. Semicap case 的 ASML 缺口被误判为静默缺证
   - ASML 不在当前本地 SEC manifest / MCP route scope。
   - specialist route 的 `input_coverage_summary.focus_ticker_source_gap_reasons` 已记录 `ASML: not_in_manifest_for_mcp_route_scope`。
   - 但 real-chain eval 的 comparative primary visibility gate 只读全局 `source_gaps`，没有读取 route-level coverage summary，导致 fundamental/risk 专员对 ASML 被误判为 missing。

## Work Completed

代码修复：

- `src/sec_agent/multi_agent_router.py`
  - deep research 基础 activation plan 默认激活 `risk_counterevidence_analyst`。
  - risk 在 deep research 中保留为 supporting / strong policy，而不是只在显式风险词出现时才激活。

- `src/sec_agent/research_lead_llm.py`
  - `_route_request_requires_risk_lens()` 对 `deep_research` 返回 true。
  - 确保 Research Lead 即使从标准 memo 被 relationship source 推高为 deep research，也不会把 risk 专员剪掉。

- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - comparative primary visibility gate 增加 route-level `input_coverage_summary.focus_ticker_source_gap_reasons` 读取。
  - source-gap ticker 会带 `focus_ticker_primary_source_gap_reasons` 写入 case score，区分“缺公开源覆盖”和“静默缺证”。

测试补充：

- `tests/test_multi_agent_research_lead_llm.py`
  - relationship source 推高到 deep research 后必须保留 `risk_counterevidence_analyst`。

- `tests/test_multi_agent_real_llm_chain_eval.py`
  - 比较分析中如果某 ticker 没有 primary SEC row，但 route coverage 已明确给出 source gap，specialist quality gate 应通过，并保留 gap reason。

## Result And Evidence

Targeted tests:

- `python -m pytest tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_activation_plan.py -q`
  - `49 passed`
- `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py -q`
  - `29 passed`
- `python -m pytest tests/test_vnext_case_catalog_replay_gate.py tests/test_vnext_50_case_catalog.py tests/test_runtime_bridge_contracts.py::test_task_worker_supports_catalog_eval_ids_and_case_id_filters -q`
  - `8 passed`
- Related pre-checks:
  - replay gate / catalog gate `7 passed`
  - runtime bridge + Milvus config targeted tests `10 passed`

真实 Workbench full-chain rerun:

```powershell
$env:FINSIGHT_MILVUS_RUNTIME_CONFIG='configs/runtime/milvus_runtime_603_local_v0_1.json'
python scripts\runtime_bridge\smoke_java_python_bridge.py `
  --task-mode workbench_eval `
  --eval-id agent_graph_vnext_r12_successor_12 `
  --run-id r12_successor_new_cases_20260614_fix_r1 `
  --case-id fin_deep_semicap_asml_amat_lrcx_klac_cycle_025 `
  --case-id fin_deep_cloud_capex_msft_amzn_googl_supplier_026 `
  --limit 0 `
  --bge-device cuda `
  --worker-run-timeout-s 7200 `
  --expected-status SUCCESS
```

Workbench summary:

- Summary path: `reports/quality/workbench_eval/r12_successor_new_cases_20260614_fix_r1_agent_graph_vnext_r12_successor_12.json`
- `status=pass`
- `gate_status=pass`
- `case_count=2`
- `pass_count=2`
- `failure_count=0`
- `failed_cases=[]`

Case-level audit:

- `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025`
  - `gate_status=pass`
  - `missing_required_agents=[]`
  - `risk_counterevidence_analyst` activated
  - `fundamental_analyst` and `risk_counterevidence_analyst` both pass specialist evidence quality
  - ASML is recorded as source gap with reason `not_in_manifest_for_mcp_route_scope`

- `fin_deep_cloud_capex_msft_amzn_googl_supplier_026`
  - `gate_status=pass`
  - `missing_required_agents=[]`
  - `risk_counterevidence_analyst` activated
  - All required specialists pass: fundamental, industry/supply-chain, market, product/technology, risk/counterevidence
  - Milvus runtime status `local_available`, location `local`

## Follow-Up And Safety Notes

- This run is a 2-case R12 activation gate, not the final 12-case successor gate or 50-case release gate.
- Generated outputs under `reports/quality/`, `reports/logs/`, and `eval/sec_cases/outputs/` remain runtime artifacts and should not be staged by default.
- The long wall time was mostly from live LLM full-chain execution; no fallback or timeout masking was introduced.
- Next step should expand from this repaired 2-case gate to the planned 12-case successor gate, then broader release gate, while preserving root-cause-first failure handling.
