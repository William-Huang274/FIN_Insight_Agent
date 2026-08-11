# P33-1.2 Sandbox / Resource Scheduler Fixture

Date: 2026-07-05

## Prompt

Continue P33 after P33-1.1. The next deferred P32 contract is `l3_sandbox_resource_scheduler_contract_v0_1`. The work must follow Project OS / Global Stewardship: no paid full-chain, no weak fallback, and no promotion unless the contract reaches its own `L4_scope_pass`.

## Decision

Treat P33-1.2 as a no-paid deterministic runtime-alignment fixture. The fixture ties together:

- S2 `ToolGateway` / `SandboxPolicy` / `ApprovalPolicy` / `ToolInvocationLedger`;
- P12 durable runtime / HIL / resource router rows;
- R5 deterministic GPU BGE queue and CPU spillover scheduler;
- AgentInformationEconomy token-budget preflight;
- Project OS full-chain preflight as a fail-closed expensive-run guard.

The goal is not to prove cloud/Kubernetes/vLLM production scheduling. The goal is to prove FIN can safely route tools/model-like resources with auditable permission, queue, budget, spillover and failure rows before entering runtime.

## Root-Cause Repair

The first repo-level P33-1.2 manifest was blocked because S2 returned `S2_blocked`.

Root cause:

- S2 gate `blocked_tool_calls_ledgered` compared total historical rows in the whole `tool_invocations` table with the current fixture decisions.
- The real repo SQLite store already contained historical tool rows from previous slices, so S2 was falsely blocked even though current task-scoped rows were correct.

Fix:

- `src/sec_agent/r53_r60_tool_sandbox_spine.py` now compares `s2_scope_task_tool_sandbox` scoped persisted rows with current decisions.
- `tests/test_r53_r60_tool_sandbox_spine.py` adds a regression where historical tool rows exist before `build_s2_gate(...)`; S2 still passes.

This is a root-cause fix, not a fallback. The gate remains strict but is now scoped to the artifact it evaluates.

## Work Completed

- Added `src/sec_agent/p33_sandbox_resource_scheduler_fixture.py`.
- Added `scripts/engineering/run_p33_sandbox_resource_scheduler_fixture.py`.
- Added `tests/test_p33_sandbox_resource_scheduler_fixture.py`.
- Generated `data/manifests/p33_sandbox_resource_scheduler_fixture_v0_1.json`.
- Generated `docs/internal/vnext_20260610/p33_sandbox_resource_scheduler_fixture_report.zh-CN.md`.
- Updated `scripts/engineering/validate_p32_registry_promotion.py` to accept the P33-1.2 manifest as L4 fixture proof.
- Updated `tests/test_p32_registry_promotion_validation.py`.
- Updated `docs/project_os/p32_active_registry_promotion_ledger.jsonl`: `l3_sandbox_resource_scheduler_contract_v0_1` is now `active_registry_ready_runtime_alignment_only`.
- Updated P33 source docs, Project OS context/capability ledgers, internal README and master checklist.

## Result

The P33-1.2 fixture passed:

- S2 release decision: `S2_L4_scope_pass`.
- P12 release decision: `P12_L4_scope_pass_runtime_drill_ready`.
- P33 release decision: `P33_1_2_L4_scope_pass_sandbox_resource_scheduler_fixture`.
- Gate failures: `0`.
- Tool policy: forbidden actor/tool/domain/path/credential/unknown-tool attempts all fail closed and are ledgered.
- Human approval: high-risk local execution is blocked before approval and allowed after recorded approval.
- Resource routing: route policies, queue events and budget rows are visible.
- Scheduler: CUDA BGE slot use, CPU spillover and queued-wait paths are both audited.
- Budget preflight: high-token / broad specialist fanout is blocked before paid model calls.
- Project OS full-chain preflight: remains `blocked` because P30 full-chain blockers are open; this is correct and does not block this no-paid component fixture.

## Validation

Commands run:

```powershell
python -m pytest tests/test_r53_r60_tool_sandbox_spine.py tests/test_p33_sandbox_resource_scheduler_fixture.py -q
python -m py_compile src/sec_agent/r53_r60_tool_sandbox_spine.py src/sec_agent/p33_sandbox_resource_scheduler_fixture.py scripts/engineering/run_p33_sandbox_resource_scheduler_fixture.py
python scripts/engineering/run_p33_sandbox_resource_scheduler_fixture.py
```

Results:

- S2 + P33-1.2 targeted regression: `9 passed`.
- Official P33-1.2 fixture manifest/report generation: `status=pass`.

No paid LLM, no full-chain and no broad case run was executed.

## Boundary

This proves runtime alignment for the sandbox/resource scheduler contract only. It does not prove:

- cloud / Kubernetes / vLLM production scheduling;
- all production tools;
- paid full-chain readiness;
- memo insight density or model quality.

## Next Step

Proceed to `P33-1.3 capital_market_feedback` with the same no-paid deterministic fixture discipline.
