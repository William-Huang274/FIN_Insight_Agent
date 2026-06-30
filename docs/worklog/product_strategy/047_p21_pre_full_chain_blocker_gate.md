# P21 Pre-Full-Chain Blocker Gate

Date: 2026-06-30

## Prompt

The user confirmed that the five audit gaps should all be handled under the updated enterprise-grade worklog rules, and explicitly rejected treating bounded-scope data/pack gaps as optional follow-up before broad 20-50 case full-chain testing.

## Decision

Before doing broad full-chain eval, the project needs a machine-readable blocker gate. The gate should not claim product readiness. Its job is to:

- register the five blockers as durable rows;
- make `full_chain_broad_eval_allowed=false` while blockers are open;
- allow deterministic node tests, pack-level tests, and only targeted integration smoke;
- block using 20-50 full-chain cases as research-quality or product-release evidence.

## Work Completed

Added P21 runtime artifacts:

- `src/sec_agent/r53_r60_pre_full_chain_blocker_gate.py`
- `scripts/engineering/build_r53_r60_p21_pre_full_chain_blocker_gate.py`
- `tests/test_r53_r60_pre_full_chain_blocker_gate.py`

Generated P21 artifacts:

- `configs/r53_r60/p21_pre_full_chain_blocker_gate_schema_v0_1.json`
- `data/manifests/r53_r60_current_status_overlay_v0_1.jsonl`
- `data/manifests/r53_r60_current_release_board_v0_1.jsonl`
- `data/manifests/r53_r60_p21_pre_full_chain_blockers_v0_1.jsonl`
- `data/manifests/r53_r60_p21_pre_full_chain_blocker_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_p21_pre_full_chain_blocker_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_p21_pre_full_chain_blocker_gate.zh-CN.md`

The five blockers are:

1. `B01-machine-readable-backlog-status-parity`
2. `B02-p20b-owned-root-cause-open`
3. `B03-r-source-doc-status-reconciliation`
4. `B04-prd-product-acceptance-not-met`
5. `B05-depth-packs-before-broad-full-chain`

## Result

The real repo build produced:

- `status=pass` for blocker registration only;
- `closeout_level=L4_scope_pass_for_blocker_registration_only`;
- `full_chain_broad_eval_allowed=false`;
- `blocker_count_open=3/5`;
- `not_allowed_while_blocked` includes `20_50_case_full_chain_quality_claim`, `product_release_claim`, and `automation_from_stale_release_board`;
- S0 board drift is captured with real status counts: demand map `planned=57 / ready_for_implementation=4`, implementation tasks `planned=171 / ready_for_implementation=12`, release board `blocked_by_dependencies=10 / ready_to_start=1`.
- `B01-machine-readable-backlog-status-parity` is closed by the new current-status overlay, which covers S0-S10, P11-P19, P20, P20b, and P21 without rewriting the historical S0 board.
- `B02-p20b-owned-root-cause-open` is closed by the D02/D03 upstream repairs: ambiguous large bare USD facts are rejected before writer visibility, and MemoLogicPlan carries answer-first/evidence-to-thesis fields into the writer payload.

## Verification

- `python -m pytest tests/test_r53_r60_pre_full_chain_blocker_gate.py -q` -> `3 passed`
- `python -m compileall -q src\sec_agent\r53_r60_pre_full_chain_blocker_gate.py scripts\engineering\build_r53_r60_p21_pre_full_chain_blocker_gate.py` -> pass
- `python scripts\engineering\build_r53_r60_p21_pre_full_chain_blocker_gate.py --root .` -> pass, with broad full-chain blocked
- Absolute-path audit on generated P21 blocker artifacts -> no repo-local absolute path found

## Remaining Work

P21 closes the machine-readable status overlay blocker (`B01`) and, after the P20b D02/D03 repair, the owned root-cause blocker (`B02`). It does not close the remaining three blockers, and it prevents them from being hidden by later broad full-chain runs.

Next repair sequence:

1. `P22-source-doc-status-reconciliation`: R55/R57/R58/R59/R60 demand row status mapping.
2. `P23-real-product-dogfood-and-frontend-e2e`.
3. `P24/P25 pack-depth gates before broad full-chain quality regression`.

## Safety Notes

- No LLM or full-chain test was run.
- The ignored `reports/r53_r60_p20_deepseek_smoke/` directory remains local generated output.
