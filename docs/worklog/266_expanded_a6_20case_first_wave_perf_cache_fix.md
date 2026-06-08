# 266 Expanded A6 20case First-Wave Performance Cache Fix

Date: 2026-06-08

## Prompt

用户要求如果 4case 已通过就继续 20case 小并发测试；如果没有通过或遇到问题，先修再继续，不要盲跑。

## Decision

- 不直接扩跑 20case。先复盘 backend first-wave 两个单 case 的性能失败。
- `20260608_a6_20case_backend_w01b_exact_jpm` 和 `20260608_a6_20case_backend_w01b_focused_amzn` 均为 performance-only fail，scope/gap/质量类 gate 未暴露失败。
- root cause 不是 DuckDB exact ledger，也不是 GPU BGE 算力不足；主要是 resident SEC retrieval 每条新 query 重复读取/编译全量 manifest / project inventory，并且工具 trace 没有记录 ledger / SEC tool elapsed，导致 attribution 不清。
- 先修可观测性和 resident cache，再重跑 first-wave；不要继续提交后续 18 个 case。

## Work Completed

- `src/sec_agent/mcp_tool_registry.py`
  - 为 `sec_query_exact_value_ledger` 增加 `elapsed_ms`。
  - 为 `sec_search_filings` 增加 `elapsed_ms`、`registry_timing_ms` 和 query-plan stage timing 透传。
  - 为 `_read_manifest_rows()` 增加文件 token cache，避免每个 SEC tool call 在 overlay 阶段重复扫描全量 manifest。
- `scripts/cloud/sec_agent_interactive.py`
  - 为 `build_query_plan_for_graph()` 增加 manifest rows、available scope、project inventory、source gaps 的 resident 内存 cache。
  - 去掉 cached project inventory 的深拷贝；planner 路径按只读对象复用。
  - 暴露 `query_plan_timing_ms` 以定位 planner 内部耗时。
- `src/sec_agent/multi_agent_runtime.py`
  - 将 SEC search / exact ledger elapsed 和 registry/resident timing 写入 tool runtime summary。
- `src/sec_agent/mcp_resident_worker.py`
  - health cache snapshot 增加 `sec_manifest_rows_cache_size`。

## Evidence

### Failed first-wave before fix

- `20260608_a6_20case_backend_w01b_exact_jpm`
  - Case elapsed: `267792 ms`.
  - Tokens: `0`.
  - Failed only `performance.case_elapsed_ms_lte`.
  - Direct ledger repeat: first `680 ms`, then `74/73 ms`; ledger is not the bottleneck.
- `20260608_a6_20case_backend_w01b_focused_amzn`
  - Case elapsed: `297618 ms`.
  - Tokens: `30294`.
  - Failed only `performance.case_elapsed_ms_lte`.

### SEC retrieval diagnosis

Before cache fix, warm resident new-query SEC 8-K retrieval still spent about `60 s` in `build_query_plan`.

After instrumentation:

- Cold probe before registry manifest cache:
  - Total: `158418 ms`.
  - `build_query_plan`: `64608 ms`.
  - `query_plan_detail.manifest_rows`: `47011 ms`.
  - `retrieve_context_for_graph`: `93448 ms`, with BGE/context resource load included.
- Warm probe before registry manifest cache:
  - Total: `13491 ms`.
  - `query_plan_detail` stages were near-zero, but `_overlay_sec_search_contract()` still reread manifest.

After adding manifest cache in `mcp_tool_registry.py`:

- Cold probe:
  - Total: `146679 ms`.
  - `query_plan_detail.manifest_rows`: `39256 ms`.
  - `retrieve_context_for_graph`: `90745 ms`.
  - Resident `sec_manifest_rows_cache_size=1`.
- Warm probe:
  - Total: `1424 ms`.
  - `build_query_plan`: `1124 ms`.
  - `retrieve_context_for_graph`: `286 ms`.
  - `context_cache_hit=true`.

This makes low-concurrency 20case continuation feasible after one resident warmup.

## Cloud State

- Resident worker was restarted with updated code; latest observed PID: `34913`.
- Workbench backend health was reachable before the rerun attempt at `http://127.0.0.1:8775/api/health`.
- Submitted first-wave rerun jobs:
  - `20260608_a6_20case_backend_w01c_exact_jpm`
  - `20260608_a6_20case_backend_w01c_focused_amzn`
- While polling these jobs, SSH started closing before the SSH banner. Port `12353` remained TCP-reachable, but `plink -v` showed remote close immediately after TCP connect.
- Because job status could not be queried, `w01c` is not accepted as pass/fail evidence yet.

## Verification

Local:

- `python -m pytest -q tests\test_workbench_expanded_a6_eval.py tests\test_workbench_backend.py tests\test_sec_agent_mcp_runtime_tools.py`
  - `55 passed`.
- `python -m pytest -q tests\test_workbench_expanded_a6_eval.py tests\test_workbench_backend.py tests\test_sec_agent_mcp_runtime_tools.py tests\test_multi_agent_real_llm_chain_eval.py`
  - `75 passed`.

Cloud:

- `py_compile` passed for synced `scripts/cloud/sec_agent_interactive.py`, `src/sec_agent/mcp_tool_registry.py`, `src/sec_agent/mcp_resident_worker.py`, and `src/sec_agent/multi_agent_runtime.py`.
- Warm resident SEC probe passed with `1424 ms` wall time after cache fix.

## Follow-Up

- Wait for cloud SSH to recover, then poll the two `w01c` jobs before submitting anything else.
- If `w01c` passes, continue 20case in max-2 small waves.
- If `w01c` fails, inspect case artifacts first; do not blind-run the remaining cases.
- Consider lowering `WORKBENCH_MAX_ACTIVE_JOBS` to `1` if SSH/backend instability repeats under concurrency, because current priority is reliable evidence over throughput.
