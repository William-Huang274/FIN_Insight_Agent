# P12 Durable Runtime + HIL + Resource Router L4 Scope Artifacts

Date: 2026-06-30

## Scope

P12 closes the post-S10 `P-R56-001 durable_agent_runtime` gap at its own `L4_scope_pass` level. The goal is to prove that the current runtime can execute a deterministic long-running research drill through the SQL-final `FinSightResearchRuntimeFacade` with:

- runtime facade and graph-node bindings;
- checkpoint / resume bridge;
- human interrupt and approval ledger;
- resource/model route policy, queue event and budget ledger;
- replay attempt from the runtime task spine;
- derived trace export records for OpenTelemetry / Langfuse / Phoenix-style observability.

This is not a full production LangGraph migration. P12 proves the durable runtime contract and drill; P13/P14/P15 still need to wire real graph nodes, ContextEngine, retrieval/data plane and Workbench product flows through the same runtime.

## Implemented Files

- `src/sec_agent/r53_r60_durable_runtime_hil_resource_router.py`
- `scripts/engineering/build_r53_r60_p12_durable_runtime_hil_resource_router.py`
- `tests/test_r53_r60_durable_runtime_hil_resource_router.py`

Generated artifacts:

- `configs/r53_r60/p12_durable_runtime_hil_resource_router_schema_v0_1.json`
- `data/manifests/r53_r60_p12_durable_runtime_hil_resource_router_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_p12_durable_runtime_hil_resource_router_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_p12_durable_runtime_hil_resource_router_l4_scope_pass.zh-CN.md`

Runtime DB:

- `data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`

The runtime DB is a local/private generated store and is intentionally not committed.

## Runtime Objects

New P12 tables:

- `durable_runtime_metadata_p12`
- `runtime_facade_bindings_p12`
- `graph_node_runtime_bindings_p12`
- `checkpoint_bridge_records_p12`
- `human_interrupt_records_p12`
- `human_approval_decisions_p12`
- `resource_model_route_policies_p12`
- `resource_queue_events_p12`
- `model_budget_ledger_p12`
- `runtime_replay_attempts_p12`
- `trace_export_records_p12`
- `runtime_acceptance_records_p12`
- `runtime_readiness_reports_p12`
- `runtime_gate_results_p12`

Drill nodes:

- `research_lead_objective_contract`
- `retrieval_evidence_operator`
- `product_specialist_pack`
- `lead_review_checkpoint`
- `memo_logic_plan`

Route classes:

- `lead_planning_high_reasoning`
- `retrieval_embedding_gpu_queue`
- `specialist_analysis_balanced`
- `memo_render_cost_controlled`

## Result

Real builder:

```text
python scripts\engineering\build_r53_r60_p12_durable_runtime_hil_resource_router.py --root .
```

Closeout result:

- `release_decision=P12_L4_scope_pass_runtime_drill_ready`
- `closeout_level=L4_scope_pass`
- `runtime_status=durable_runtime_drill_pass`
- `hil_status=human_interrupt_resume_pass`
- `resource_router_status=resource_router_ledger_pass`
- `replay_status=replayable`
- `full_runtime_migration_status=partial_migration_runtime_drill_only`
- gates: `12 pass / 0 fail`

Counts:

- runtime facade bindings: `1`
- graph node bindings: `5`
- checkpoint bridge records: `2`
- human interrupt records: `1`
- human approval decisions: `1`
- route policies: `4`
- resource queue events: `5`
- budget records: `1`
- replay attempts: `1`
- trace exports: `3`
- acceptance records: `5`

## Bugs Found And Fixed

1. `runtime_readiness_reports_p12` had 14 columns but the insert statement had 13 placeholders. Fixed before real builder execution.
2. `seed_p12_metadata` and `clear_p12_rows` were referenced but missing. Added explicit metadata seeding and P12-table reset.
3. HIL resume returned the drill task to `pending`; the runtime then attempted `pending -> succeeded`, which violates the S1 state machine. Fixed to enforce `paused -> pending -> running -> succeeded`.

## Verification

```text
python -m py_compile src\sec_agent\r53_r60_durable_runtime_hil_resource_router.py scripts\engineering\build_r53_r60_p12_durable_runtime_hil_resource_router.py
python -m pytest tests\test_r53_r60_durable_runtime_hil_resource_router.py -q
```

Result:

- `5 passed`

## Remaining Boundary

P12 known gaps are explicit:

- `full_langgraph_node_migration`: P12 proves runtime contracts through a deterministic drill; every production graph node is not yet migrated.
- `real_gpu_queue_pressure`: P12 records resource routes and queue events, but does not run cloud high-concurrency GPU scheduling.

The next slices should not weaken these into hidden fallback behavior. They should wire actual graph/runtime/data/workbench paths through the same ledgered contract and collect real pilot telemetry.
