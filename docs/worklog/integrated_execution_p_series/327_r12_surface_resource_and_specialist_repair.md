# 327 R12 Surface Resource And Specialist Repair

Date: 2026-06-14

## Prompt

用户要求继续修复两项 R12 阻塞：

- 正文禁止渲染内部字段，新增可读性 gate，缩短 citation，并让 `MemoLogicPlan` 成为 writer 主输入。
- ASML 这类非本地 SEC 覆盖公司不能直接暴露 bounded gap；本地库缺失时应按 issuer coverage policy 先走 company IR / local exchange / regulator / SEC FPI official-source probe 边界。

## Decision

本轮不降低检索预算、不把失败隐藏成 fallback。按实际运行结果分三类处理：

- `source_gap`：本地 SEC manifest 理论上没有可用 filing 时，不能算 runtime error，要进入 issuer coverage / official-source probe 边界。
- `runtime_resource_failure`：BGE CUDA 加载或并发造成的内存压力，应通过资源调度和进程卫生解决，不能降低 evidence budget。
- `specialist_contract_failure`：专家产出的 supported observation 缺 `evidence_refs` 时，不能进 supported plan；对风险反证专家可全部降级为 unsupported 风险缺口，对基本面/产品等核心专家仍 fail closed。

## Work Completed

- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - 增加 `--evidence-operator-fanout-workers`。
  - 本地 `bge_device=cuda` + `context_runner=in_process` 默认解析为 `1` 路 evidence-operator fanout worker。
  - 在 `multi_agent_context` 和 aggregate summary 中写入 `evidence_operator_resource_policy`，使资源策略可审计。
- `src/sec_agent/workbench/job_runner.py`
  - Workbench R12/G11/load-mix eval 命令显式传递 `--evidence-operator-fanout-workers 0`。
  - `0` 表示 Python eval 根据实际 device/runner 自动决策；云端可用 env 或 metadata 显式放开。
- `src/sec_agent/runtime_bridge/task_worker.py`
  - Workbench task metadata 支持覆盖 `evidence_operator_fanout_workers`。
- `src/sec_agent/specialist_llm.py`
  - 修复 `risk_counterevidence_analyst` 全部 supported observations 缺 citation 的处理：全部降级为 `unsupported_claims`，route 可通过但不会进入 supported ClaimCard。
  - 保持核心专家 fail-closed：非 risk 专家如果所有 supported observations 都缺有效 citation，仍然 route fail。
- `src/sec_agent/mcp_tool_registry.py`
  - SEC search 在 manifest 范围内找不到可用 filings 时返回 `source_gap`，而不是 `error`。
  - 覆盖 planner 和 retrieval 两个阶段的 `No available SEC filings matched inferred scope`。
- 测试覆盖：
  - real-chain eval resource policy。
  - Workbench eval command fanout-worker pass-through。
  - SEC source-gap contract。
  - risk specialist all-no-ref salvage。
  - memo renderer readability cleanup。

## Verification

- Syntax:
  - `python -m py_compile scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py src/sec_agent/workbench/job_runner.py src/sec_agent/runtime_bridge/task_worker.py src/sec_agent/mcp_tool_registry.py src/sec_agent/langgraph_orchestrator.py`
  - `python -m py_compile src/sec_agent/specialist_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py src/sec_agent/workbench/job_runner.py src/sec_agent/runtime_bridge/task_worker.py`
- Unit / contract tests:
  - `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_workbench_job_runner.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_multi_agent_judgment_memo_verifier.py -q`
    - Result: `82 passed`
  - `python -m pytest tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_workbench_job_runner.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_multi_agent_judgment_memo_verifier.py -q`
    - Result: `128 passed`

## Live Workbench Runs

All runs used Workbench backend path through `scripts/runtime_bridge/smoke_java_python_bridge.py`, local Milvus runtime config `configs/runtime/milvus_runtime_603_local_v0_1.json`, and `--bge-device cuda`.

- `r12_successor_surface_gate_20260614_r4`
  - Status: failed as runtime process failure, not case-quality failure.
  - Evidence: run stopped after semicap grouped SEC search context preparation with native `memory allocation ... failed`.
  - Root cause class: resource / process lifecycle pressure around local CUDA BGE, plus stale smoke gateway processes.
- `r12_successor_surface_gate_20260614_r5`
  - Status: aggregate fail, `1/2` pass.
  - Cloud capex case passed.
  - Semicap failed only specialist layer:
    - `risk_counterevidence_analyst` route failed because 3 supported observations had no `evidence_refs`.
    - Evidence operators, source-gap handling, memo surface readability, run audit, Milvus runtime contract, and diagnostic gates passed.
  - Resource policy in summary:
    - `evidence_operator_fanout_workers=1`
    - `policy_name=local_cuda_serial_bge_queue`
- `r12_successor_surface_gate_20260614_r6`
  - Status: pass.
  - Metrics:
    - `case_count=2`
    - `passed=2`
    - `failed=0`
    - `pass_rate=1.0`
    - `total_tool_calls=25`
    - `real_specialist_quality_passed=2`
  - Artifact summary:
    - `reports/quality/workbench_eval/r12_successor_surface_gate_20260614_r6_agent_graph_vnext_r12_successor_12.json`
    - `eval/sec_cases/outputs/multi_agent_vnext_r12_successor_12_eval/r12_successor_surface_gate_20260614_r6/real_chain_eval_summary.json`

## Operational Notes

- Before r5/r6, terminated `53` stale `finsight.gateway.TaskGatewayServer` Java processes under `D:\temp\pytest-*`, `D:\temp\finsight_bridge_*`, and `D:\temp\finsight_r10_load_*`. These were prior test/smoke residual gateway processes, not the active workbench Python server.
- r6 latest events include one gRPC `too_many_pings` stdout line from local runtime, but final task status was `SUCCESS` and eval gate was `pass`.

## Follow-Up

- Run the broader 10-20 case R12 gate after reviewing the 2-case memo outputs for readability and investment-analysis depth.
- Add real official-source web fetch execution for non-US issuer repair once the allowed-source web operator is promoted; current result correctly converts local SEC misses to `source_gap` and issuer official-source policy boundaries, but does not claim ASML official filing facts unless fetched.
- Keep resource policy auditable in future cloud runs: local CUDA defaults to serialized BGE-backed evidence routes; cloud can explicitly set `SEC_AGENT_EVIDENCE_OPERATOR_FANOUT_WORKERS=3` or higher after load testing.
