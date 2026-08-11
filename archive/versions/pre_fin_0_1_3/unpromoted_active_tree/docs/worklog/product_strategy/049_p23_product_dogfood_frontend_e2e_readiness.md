# P23 Product Dogfood / Frontend E2E Readiness

Date: 2026-06-30

Supersession note: at this checkpoint both B04 and B05 remained open. The later P25/B05 closeout closed B05; current P21 has only B04 open.

## Prompt

Continue the post-P22 closeout sequence under the updated enterprise-grade rule: at this checkpoint, broad full-chain cases were not allowed because PRD product acceptance and the data-depth blocker had not yet closed. The immediate target was P23, the automated Workbench product journey and frontend E2E readiness slice.

## Decision

P23 should close only the automatable part of `B04-prd-product-acceptance-not-met`: Workbench API route availability, frontend route/component/build contract, and review-action write-path integrity. It must not claim real human reviewer adoption or product acceptance.

The closeout label is therefore:

- `closeout_level=L4_scope_pass_for_automated_product_journey_only`
- `product_acceptance_status=blocked_requires_real_human_review`
- `b04_status_after_p23=open_product_acceptance_required`

## Work Completed

Added P23 runtime artifacts:

- `src/sec_agent/r53_r60_product_dogfood_frontend_e2e.py`
- `scripts/engineering/build_r53_r60_p23_product_dogfood_frontend_e2e.py`
- `tests/test_r53_r60_product_dogfood_frontend_e2e.py`

Updated P21 blocker gate:

- `src/sec_agent/r53_r60_pre_full_chain_blocker_gate.py` now reads `r53_r60_p23_product_dogfood_frontend_e2e_summary_v0_1.json` into B04 observed evidence while keeping B04 open.

Generated P23 artifacts:

- `configs/r53_r60/p23_product_dogfood_frontend_e2e_schema_v0_1.json`
- `data/manifests/r53_r60_p23_product_dogfood_frontend_e2e_api_journey_rows_v0_1.jsonl`
- `data/manifests/r53_r60_p23_product_dogfood_frontend_e2e_frontend_check_rows_v0_1.jsonl`
- `data/manifests/r53_r60_p23_product_dogfood_frontend_e2e_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_p23_product_dogfood_frontend_e2e_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_p23_product_dogfood_frontend_e2e_scope_pass_human_pending.zh-CN.md`

Updated source docs and indexes:

- `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`
- `docs/architecture/agent_graph_vnext/34_r59_backend_frontend_workbench_hardening_technical_plan.zh-CN.md`
- `docs/worklog/00_internal_master_checklist.md`
- `docs/worklog/README.md`

## Root-Cause Fix

The first real P23 builder run failed even though tests passed. Root cause: the script environment added `src` to `sys.path` but not the repository root, so `apps.workbench.backend.app` could not be imported.

This was an owned entrypoint contract bug, not an external gap. The fix was to make `run_workbench_api_journey()` insert the repo root into `sys.path` during the Workbench backend import. P23 tests now cover the real API journey path.

## Result

Real repo P23 build:

- `status=pass_with_human_acceptance_blocked`
- `release_decision=P23_automated_product_journey_pass_human_dogfood_pending`
- `dependency_fail_count=0/5`
- `api_journey_fail_count=0/14`
- `frontend_fail_count=0/13`
- `frontend_warn_count=0/13`
- `gate_fail_count=0/7`
- `full_chain_broad_eval_allowed=false`

API surfaces verified:

- task center / task state / task events / task artifacts
- task drilldown / review queue / ops projection
- deliverables / dashboard projection / scope gate
- pilot dashboard / pilot action ledger
- task review action write / pilot review action write

Frontend checks verified:

- R53-R60 Workbench route anchor
- Workbench panel and Pilot Dogfood panel components
- API route strings for task, pilot, and review action paths
- Review Queue, Deliverable Studio, and Dashboard Projection labels
- Pilot panel, review action editor, answer preview styles
- fresh Vite dist build

P21 rerun after P23:

- `blocker_count_open=2/5`
- `full_chain_broad_eval_allowed=false`
- B04 includes P23 observed evidence, but remains `open_product_acceptance_required`

## Verification

- `python -m pytest tests/test_r53_r60_product_dogfood_frontend_e2e.py tests/test_r53_r60_pre_full_chain_blocker_gate.py -q` -> `8 passed`
- `python -m py_compile tests\test_r53_r60_product_dogfood_frontend_e2e.py scripts\engineering\build_r53_r60_p23_product_dogfood_frontend_e2e.py src\sec_agent\r53_r60_pre_full_chain_blocker_gate.py` -> pass
- Frontend build using bundled Node:
  - `node node_modules\typescript\bin\tsc -p tsconfig.json`
  - `node node_modules\vite\bin\vite.js build --config vite.config.ts`
  - pass
- `python scripts\engineering\build_r53_r60_p23_product_dogfood_frontend_e2e.py --root .` -> pass
- `python scripts\engineering\build_r53_r60_p21_pre_full_chain_blocker_gate.py --root .` -> pass, broad full-chain still blocked

## Remaining Work

P23 does not close PRD-level product acceptance. Remaining P21 blockers:

1. `B04-prd-product-acceptance-not-met`
   - real reviewer sessions;
   - accepted/rejected deliverables;
   - reviewer defect closure or typed-gap promotion;
   - browser visual E2E and usability review.
2. `B05-depth-packs-before-broad-full-chain`
   - ProductEvidencePack, SecondaryMarketPack, QuantLab, Deliverable Studio, retrieval/data refresh and pack-level depth gates before 20-50 broad full-chain research-quality claims.

## Safety Notes

- P23 writes automation-marked review actions with `reviewer_role=automation_e2e`; these do not count as human adoption.
- No DeepSeek or broad full-chain LLM regression was run in this slice.
- Existing local generated output `reports/r53_r60_p20_deepseek_smoke/` remains untracked and unrelated to P23.
