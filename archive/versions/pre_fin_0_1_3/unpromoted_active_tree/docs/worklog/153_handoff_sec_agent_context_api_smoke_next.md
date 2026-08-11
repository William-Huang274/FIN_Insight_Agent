# Handoff: SEC Agent ContextManager API Smoke And Load Next

## Current Status
- Local repo: `D:\FIN_Insight_Agent`.
- Current focus: SEC agent multi-turn user/session context management.
- Latest completed increment: `ContextManager` request-level smoke + small single-process load smoke.
- No secrets are stored in repo files. Do not write cloud passwords or API keys into worklogs, reports, or command snippets.
- Latest local validation did not call DeepSeek, did not use cloud, did not run GPU, and did not execute the real SEC DAG.

## What Is Now Implemented
### 1. ContextManager v1
Main files:
- `src/sec_agent/context_store.py`
- `src/sec_agent/context_manager.py`
- `src/sec_agent/__init__.py`

Implemented behavior:
- JSON-backed user/session context store.
- Per `tenant_id + user_id` user profile with:
  - `active_session_id`
  - `recent_session_ids`
  - `last_references`
  - user preferences.
- Controller-facing compact snapshots with lossless fields:
  - tenant/user/session identity
  - active answer ID
  - active scope
  - artifact state
  - resume cursor
  - source policy.
- Bounded summary/recent-turn/session-candidate hints.
- Ambiguous no-active-session references return clarification/candidates instead of guessing.
- Cross-user access returns access denied.
- User profile writes now use temp-file atomic replace with short retry. This was added after a Windows `WinError 5` surfaced during small load smoke.

### 2. Context-Managed Controller And Dispatch Eval
Main files:
- `src/sec_agent/tool_controller.py`
- `scripts/evaluate_sec_agent_context_managed_tool_controller.py`
- `scripts/evaluate_sec_agent_context_managed_dispatch_replay.py`

Implemented behavior:
- `DeepSeekToolController` can consume `runtime_context["context_snapshot"]` produced by `SecAgentContextManager`.
- Route-only eval no longer depends on hand-built runtime context.
- Dispatch replay flow validates:
  - build ContextManager snapshot
  - route tool
  - call `SecAgentToolHarness.dispatch()`
  - apply tool result back into context
  - rebuild and validate post-turn snapshot.

Latest known results:
- `reports/quality/cloud_context_managed_tool_controller_route_deepseek_v1.json`
  - `6` scenarios / `23` turns
  - tool `23/23`
  - args `23/23`
  - snapshot `23/23`
  - `failure_count=0`.
- `reports/quality/cloud_context_managed_dispatch_replay_deepseek_v1.json`
  - `6` scenarios / `23` turns
  - tool/args/snapshot/dispatch/context update all `23/23`
  - `failure_count=0`.

These DeepSeek runs were route + fixture harness dispatch only. They did not run the real SEC DAG or GPU workload.

### 3. Request-Level Handler
New file:
- `src/sec_agent/context_api.py`

Purpose:
- Provide a transport-agnostic request handler that a future FastAPI/Flask/server endpoint can call after auth.

Current request flow:
1. Build context snapshot from `tenant_id`, `user_id`, optional `session_id`, and `user_message`.
2. Return early for `clarification_required`, `access_denied`, or context errors.
3. If explicit `session_id` is provided, set it as active and reload active context.
4. Route with controller in `route_only=True` mode.
5. Dispatch selected harness tool.
6. Apply tool result back into `ContextManager`.
7. Rebuild post-turn context snapshot.

Concurrency behavior:
- v1 uses a process-local `RLock` around JSON-backed read/modify/write.
- This is acceptable for local demo/smoke.
- It is not a production multi-process concurrency guarantee.
- Before any production concurrency claim, replace JSON store locking with SQLite/Postgres/Redis transactions or a cross-process file lock.

## Latest Local Validation
### Syntax Check
Command:
```powershell
python -m py_compile src/sec_agent/context_store.py src/sec_agent/context_api.py src/sec_agent/__init__.py scripts/evaluate_sec_agent_context_api_smoke.py scripts/benchmark_sec_agent_context_api.py
```

Result:
```text
passed
```

### API Request Smoke
Script:
- `scripts/evaluate_sec_agent_context_api_smoke.py`

Command:
```powershell
python scripts/evaluate_sec_agent_context_api_smoke.py --controller-backend heuristic --output-path reports/quality/local_context_api_smoke_heuristic_v1.json
```

Output:
- `reports/quality/local_context_api_smoke_heuristic_v1.json`

Result:
```text
case_count=6
pass_count=6
all_pass=true
failure_count=0
```

Covered cases:
- no active session + ambiguous reference -> `clarification_required`
- explicit session coverage query -> `inspect_coverage`
- follow-up evidence query uses active session -> `explain_evidence`
- explicit session switch -> `get_session_state`
- follow-up reformat -> `reformat_answer`, invalidates only `rendered_answer`
- cross-user session access -> `access_denied`, no tool call.

### Small Load Smoke
Script:
- `scripts/benchmark_sec_agent_context_api.py`

Command:
```powershell
python scripts/benchmark_sec_agent_context_api.py --controller-backend heuristic --requests 120 --concurrency 8 --warmup-requests 10 --workload mixed --output-path reports/quality/local_context_api_load_heuristic_v1.json
```

Output:
- `reports/quality/local_context_api_load_heuristic_v1.json`

Result:
```text
request_count=120
concurrency=8
pass_count=120
all_pass=true
failure_count=0
throughput_rps=16.9839
p50_latency_ms=468.0
p90_latency_ms=794.8
p95_latency_ms=880.15
p99_latency_ms=1013.16
max_latency_ms=1430.0
```

Distribution:
```text
status_counts:
  completed=96
  access_denied=24

tool_counts:
  inspect_coverage=24
  explain_evidence=24
  get_session_state=24
  reformat_answer=24
  denied/no-tool=24
```

Interpretation:
- The request-level handler is stable for a single-process fixture workload.
- The measured latency is dominated by serialized JSON-backed request locking plus repeated fixture reads/writes, not model inference.
- This is a smoke/load check, not a serving benchmark for real SEC DAG execution.

### Regression After API Smoke
Commands:
```powershell
python scripts/evaluate_sec_agent_context_state_replay.py --output-path reports/quality/local_context_state_replay_after_api_smoke_v1.json
python scripts/evaluate_sec_agent_context_managed_dispatch_replay.py --controller-backend heuristic --output-path reports/quality/local_context_managed_dispatch_replay_after_api_smoke_heuristic_v1.json
```

Results:
```text
local_context_state_replay_after_api_smoke_v1.json:
  7/7 passed

local_context_managed_dispatch_replay_after_api_smoke_heuristic_v1.json:
  6 scenarios / 23 turns
  tool=23/23
  args=23/23
  snapshot=23/23
  dispatch=23/23
  context_update=23/23
  failure_count=0
```

## Key Reports And Ledgers
- `reports/quality/local_context_api_smoke_heuristic_v1.json`
- `reports/quality/local_context_api_load_heuristic_v1.json`
- `reports/quality/local_context_state_replay_after_api_smoke_v1.json`
- `reports/quality/local_context_managed_dispatch_replay_after_api_smoke_heuristic_v1.json`
- `reports/quality/cloud_context_managed_tool_controller_route_deepseek_v1.json`
- `reports/quality/cloud_context_managed_dispatch_replay_deepseek_v1.json`
- `reports/model_runs/20260523_sec_agent_context_managed_deepseek_route_v1.md`
- `reports/model_runs/20260523_sec_agent_context_managed_deepseek_dispatch_replay_v1.md`

## Worklog Updates
Updated files:
- `docs/worklog/152_sec_agent_context_manager_state_replay_v1.md`
- `docs/worklog/00_internal_master_checklist.md`
- `docs/worklog/README.md`

Checklist state:
- Completed:
  - JSON-backed `ContextManager` v1.
  - Deterministic state replay suite.
  - Cloud ContextManager state replay.
  - Context-managed controller evaluator.
  - DeepSeek route-only over context-managed controller evaluator.
  - Context-managed dispatch replay.
  - DeepSeek over context-managed dispatch replay.
  - API/request-level ContextManager smoke.
  - Small single-process ContextManager API load smoke.
- Open:
  - Replace JSON-store request locking with DB/Redis/file-lock backed transactions before any production concurrency claim.
  - Revisit transcript / investor-presentation source expansion only after non-contiguous follow-up validation passes.
  - Validate earlier-node resume from a real partial replay, especially `build_coverage_matrix` or `build_judgment_plan`.

## Important Caveats
- Current request handler is not a web server. It is an in-process boundary for future API integration.
- Current API smoke uses heuristic controller, not DeepSeek. DeepSeek was already validated for context-managed route and dispatch replay in the previous cloud runs.
- Current load smoke uses fixture harness dispatch, not real SEC DAG execution.
- JSON store + process-local lock does not protect multi-process workers.
- Do not claim production concurrency until DB/Redis/cross-process locking is implemented and tested.
- Do not continue into multi-source expansion until the current multi-turn/context path remains stable and the user confirms.

## Suggested Next Window Prompt
```text
Continue from docs/worklog/153_handoff_sec_agent_context_api_smoke_next.md.

Goal:
1. Review the ContextManager API smoke/load implementation and current reports.
2. Decide whether to run a small cloud DeepSeek request-level API smoke, or first replace JSON-store locking with a more production-like store/lock.
3. Do not run real SEC DAG/GPU unless explicitly requested.
4. Do not write any API keys or cloud passwords into repo files.

Relevant files:
- src/sec_agent/context_api.py
- src/sec_agent/context_store.py
- src/sec_agent/context_manager.py
- scripts/evaluate_sec_agent_context_api_smoke.py
- scripts/benchmark_sec_agent_context_api.py
- docs/worklog/152_sec_agent_context_manager_state_replay_v1.md
- reports/quality/local_context_api_smoke_heuristic_v1.json
- reports/quality/local_context_api_load_heuristic_v1.json

Current validation:
- API smoke: 6/6
- small load smoke: 120/120, 8 concurrency, failure_count=0
- state replay regression: 7/7
- context-managed dispatch replay regression: 23/23
```
