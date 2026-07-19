# P33 Humanmade Gold Set Runtime Quality Gate

Date: 2026-07-06

## Scope

This work implements the next P33 no-paid repair layer requested after the Humanmade Gold Set matrix audit:

1. artifact-backed `HumanmadeGoldSetAudit`;
2. `BriefingPackQualityGate`;
3. AI/Semis human source ledger runtime slots;
4. rubric cases compiled into vertical playbook runtime contracts;
5. negative cases compiled into deterministic failure gates.

The pass condition is deliberately stricter than "runs without error": quality must approach the Humanmade Gold Set before paid Memo Writer or full-chain is allowed.

## Implementation

- Added `src/sec_agent/humanmade_gold_set_runtime.py`.
- Added `scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py`.
- Added `tests/test_p33_humanmade_gold_set_runtime_quality_gate.py`.
- Wired `HumanmadeGoldSetAudit` into `src/sec_agent/memo_llm.py` before Memo Writer model calls.
- Wired the same gate into `scripts/eval_multi_agent/run_p33_memo_writer_node_from_aggregate.py`.
- Generated:
  - `docs/project_os/humanmade_gold_set_runtime_quality_gate_v0_1.json`;
  - `docs/project_os/ai_semis_human_source_runtime_slots_v0_1.json`;
  - `docs/internal/vnext_20260610/p33_humanmade_gold_set_runtime_quality_gate_v0_1.zh-CN.md`.

## Result

The gate is active, but the current accepted artifacts do not pass.

```text
HumanmadeGoldSetAudit.status = fail
pre_writer_decision.allow_paid_memo_writer = false
BriefingPackQualityGate.status = fail
BriefingPackQualityGate.fail_count = 6
NegativeFailureGates.status = pending_final_memo
NegativeFailureGates.fail_count = 0
NegativeFailureGates.pending_final_memo_count = 1
```

The `pending_final_memo` negative gate is expected because no new final memo was generated. It will run once a final memo artifact exists.

## Current Quality Failures

The current briefing pack fails six Humanmade Gold Set lanes:

- `product_architecture_competition`: product layer is still taxonomy/context-heavy; `product_runtime_fact_count=0`.
- `customer_deployment_adoption`: deployment rows remain mostly relationship scope/hypothesis or lack official customer/order/config evidence.
- `dell_financial_quality_bridge`: DELL AI server margin quality bridge lacks mix, GPU pass-through cost, and backlog conversion evidence.
- `semicap_foundry_readthrough`: ASML/LRCX/AMAT/KLAC read-through remains broad context or route/parser boundary.
- `market_expectation_price_in`: valuation, ownership/positioning, price reaction, and price-in rows are still missing or generic.
- `counter_thesis_and_what_would_change`: risk/counter-thesis remains partial and too generic.

## Important Fix During This Work

The initial negative gate scan could false-fire by reading Gold Set rule text itself, such as forbidden examples in the contract. The scanner now extracts runtime assertions only from `verified_judgment_plan`, `memo_logic_plan`, writer payload errors/warnings, and final memo text. After the fix, negative deterministic gates report `fail_count=0` on current pre-memo artifacts.

## Verification

```text
python -m py_compile src/sec_agent/humanmade_gold_set_runtime.py scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py scripts/eval_multi_agent/run_p33_memo_writer_node_from_aggregate.py src/sec_agent/memo_llm.py
python -m pytest tests/test_p33_humanmade_gold_set_runtime_quality_gate.py tests/test_p33_memo_writer_node_runner.py tests/test_p33_memo_writer_payload_preflight_runner.py -q
python scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py
python -m json.tool docs/project_os/humanmade_gold_set_runtime_quality_gate_v0_1.json
python -m json.tool docs/project_os/ai_semis_human_source_runtime_slots_v0_1.json
```

Original baseline result:

```text
6 passed
no-paid audit status = fail
allow_paid_memo_writer = false
```

2026-07-07 follow-up in `103_p33_gold_depth_runtime_assimilation.md` adds a repaired assimilated checkpoint that passes no-paid audit. This 102 entry remains the unassimilated baseline failure record.

## Boundary

No DeepSeek call, GPT call, paid Memo Writer, full-chain, model comparison, case expansion, new retrieval, crawler, or parser run was executed.

This is not a pass. It is a runtime enforcement layer that now prevents the known quality gap from being hidden by a paid writer call.

## Next Repair Direction

The next work must remain no-paid or node-level until the gate passes:

1. deepen AI/Semis source runtime slots and ProductIntelligenceGraph projection;
2. turn product architecture/spec/benchmark/deployment into investment-role graph evidence;
3. upgrade specialist answer-exemplar contracts so outputs look like analyst briefing material;
4. add Research Lead gold-depth veto before writer;
5. rerun `HumanmadeGoldSetAudit` until `BriefingPackQualityGate` passes.
