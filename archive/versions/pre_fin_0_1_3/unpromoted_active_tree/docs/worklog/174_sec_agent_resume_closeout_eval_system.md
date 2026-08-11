# 174 SEC Agent Resume Closeout Eval System

## Prompt

用户要求在现有 10-K + latest 10-Q + 8-K + market_snapshot 基础上，完善 agent 自检和评测体系，并按这些标准设计多用例考核当前全链路各环节、各维度可靠性。当前项目准备做第一版收口用于投简历。

## Decision

新增一个聚合型 closeout readiness 入口，不改主链路，不加业务兜底。它只编排既有 deterministic eval/smoke，并把 full-source DeepSeek 真实运行作为可选 saved-run inspection 接入同一份报告。

这样区分三类证据：

- 本地代码/状态机可靠性：必须可重复跑，失败即 blocker。
- 私有数据/云端 full-source 产物：本地缺失时标 warn/skipped；用户或云端提供 run dir 后才作为 full-source 主结论。
- Planner/market main-chain 本地诊断：作为阶段质量信号，不替代真实 DeepSeek full-source benchmark。

## Work Completed

- Added `scripts/evaluate_sec_agent_resume_closeout_readiness.py`.
  - Aggregates ContextManager state replay, request-level API smoke, context-managed dispatch replay, fixture-backed tool harness dispatch, targeted pytest, planner diagnostic, local market main-chain smoke, source inventory inspection, and optional saved full-source run inspection.
  - Reports `pass` / `warn` / `skipped` / `fail`, with blocker status only for critical local checks or provided saved-run failures.
  - Checks source inventory for 10-K/latest 10-Q/8-K/market_snapshot artifacts and market fields such as returns, drawdown, volatility, valuation, and latest-10Q event-window returns.
  - Checks saved full-source run artifacts: graph state, coverage matrix, ledger, Judgment Plan, model outputs, rendered answer, post-gates, market context rows, gate failures, fallback answer count, and evidence-boundary labels.
- Added `eval_sets/sec_agent_resume_closeout_eval_v1.json`.
  - Defines closeout dimensions and 7 multi-use cases covering full-source memo, full30 broad scan, SEC-only negative control, 8-K management explanation, market valuation peer analysis, multi-turn context, and partial resume.
- Added `eval_sets/sec_agent_resume_closeout_planner_eval_v1.jsonl`.
  - Planner diagnostic subset for mixed SEC/recent market source questions.
- Added `docs/eval/sec_agent_resume_closeout_eval_v1.md`.
  - Documents closeout standards, command usage, dimensions, case coverage, and interpretation rules.
- Added `tests/test_resume_closeout_readiness.py`.
  - Unit tests for manifest summary, market evidence summary, saved-run inspection, and aggregate status logic.

## Expected Validation

Local:

```powershell
python -m py_compile scripts/evaluate_sec_agent_resume_closeout_readiness.py
python -m pytest tests/test_resume_closeout_readiness.py -q
python scripts/evaluate_sec_agent_resume_closeout_readiness.py
```

## Local Validation Result

Run on 2026-05-26 local workspace:

```text
python -m py_compile scripts/evaluate_sec_agent_resume_closeout_readiness.py scripts/run_sec_free_query_planner_eval.py src/sec_agent/context_manager.py src/sec_agent/tool_controller.py src/sec_agent/tool_harness.py
python -m pytest tests/test_resume_closeout_readiness.py -q
python scripts/evaluate_sec_agent_context_state_replay.py --output-path reports/quality/resume_closeout_debug_context_state_replay.json --fixture-root reports/quality/resume_closeout_debug_context_state_replay_fixture --clean-fixtures
python scripts/evaluate_sec_agent_context_managed_dispatch_replay.py --output-path reports/quality/resume_closeout_debug_context_managed_dispatch.json --fixture-root reports/quality/resume_closeout_debug_context_managed_dispatch_fixture --controller-backend heuristic --clean-fixtures
python scripts/evaluate_sec_agent_resume_closeout_readiness.py
```

Observed:

- New unit tests: `5 passed`.
- Context state replay: `7/7`, all pass.
- Context-managed dispatch replay: `23/23`, all pass.
- Aggregate readiness report: `reports/quality/resume_closeout/20260526_031829_resume_closeout_readiness_local_v1.json`.
- Aggregate status: `warn`, with `blocker_fail_count=0`, `pass=6`, `warn=2`, `skipped=1`.
- Critical local checks passed: ContextManager state replay, request API smoke, context-managed dispatch, tool harness dispatch, and source/period/market contract pytest (`57 passed` inside aggregate run).
- Market main-chain local smoke passed with `context_row_count=1417`, `market_context_row_count=5`, `ledger_row_count=25`, `primary_task_support_complete=true`, `market_snapshot_support_complete=true`, `source_coverage_gaps=[]`.

Warnings:

- `source_inventory_artifacts`: local workspace does not contain the full-source 8-K earnings-release manifest/index expected by the closeout full-source profile; this should be rechecked on cloud or after syncing private artifacts.
- `planner_contract_eval_local`: heuristic diagnostic does not meet the closeout planner threshold, mainly because the diagnostic expected 2023-2027 while local planner/inventory resolves a narrower local scope. This is not promoted as a DeepSeek planner result.
- `saved_full_source_deepseek_run`: skipped because no saved cloud full-source run directory was passed to the local command.

Root-cause fixes made during validation:

- `ContextManager` now treats `market_snapshot_context` as optional in artifact-state summaries instead of reporting it as missing for SEC-only/fixture sessions.
- Tool controller stage-resume guard now recognizes Chinese interrupted-run phrasing such as `没跑完` / `不要从头`.
- Tool harness `resume_analysis` now rejects empty/non-file `state_path` before attempting to read a directory path.
- `run_sec_free_query_planner_eval.py` now exposes `--source-gap-path`, matching the interactive inventory contract it calls.

Cloud/full-source after a DeepSeek run exists:

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir /root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/<full_source_run>/<run_id> \
  --require-full-source-artifacts
```

## Current Caveats

- Local repo currently may not contain the full-source 8-K earnings-release manifest/index; the readiness script intentionally reports this as warning/skipped unless `--require-full-source-artifacts` is set.
- The local planner diagnostic uses `heuristic` by default and is not a substitute for the DeepSeek planner/full-source benchmark.
- Generated reports under `reports/quality/resume_closeout/` are runtime artifacts and should not be staged by default.

## Follow-Up

- Run the new closeout readiness entry locally and record the produced report path.
- On cloud, pass the latest full-source DeepSeek run directory into `--saved-full-source-run-dir` and require full-source artifacts before claiming resume-ready full-chain status.
- Add at least one saved run for each closeout case family before final project packaging.
