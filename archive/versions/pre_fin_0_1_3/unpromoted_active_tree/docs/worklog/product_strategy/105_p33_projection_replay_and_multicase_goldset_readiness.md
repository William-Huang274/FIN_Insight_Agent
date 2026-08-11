# P33 Projection Replay and Multi-case Gold-set Readiness

Date: 2026-07-07

## Scope

User asked to finish the single-case renderer projection, final verifier projection and Workbench projection, then start the multi-case Humanmade Gold Set work. The multi-case work must not skip the issues left open in the single case: evidence depth must be repaired, and specialists must pass a fresh all-specialist gold pass rather than relying on targeted composite output.

This step intentionally did not run another paid LLM call, full-chain case, model comparison or case expansion. The goal was to replay the already accepted scoped Memo Writer artifact through the final projections and make the multi-case readiness boundary explicit.

## Work Completed

1. Added `src/sec_agent/p33_memo_projection_replay.py`.
   It replays an accepted Memo Writer node artifact through renderer, final verifier and Workbench projection logic without calling a model.

2. Added `scripts/eval_multi_agent/run_p33_memo_projection_replay.py`.
   The runner emits:
   - `docs/project_os/p33_single_case_projection_replay_v0_1.json`
   - `docs/internal/vnext_20260610/p33_single_case_projection_replay_v0_1.zh-CN.md`
   - `docs/project_os/p33_multicase_goldset_readiness_v0_1.json`
   - `docs/internal/vnext_20260610/p33_multicase_goldset_readiness_v0_1.zh-CN.md`

3. Added `tests/test_p33_memo_projection_replay.py`.
   The tests cover renderer projection, final verifier projection, Workbench projection and the multi-case readiness block.

4. Fixed an owned renderer projection defect in `src/sec_agent/langgraph_orchestrator.py`.
   The renderer previously recomputed required-item answers from weak evidence matching and could downgrade writer-ready `MemoLogicPlan.required_item_answer_plan` material into no-promotable-evidence text. The fix prioritizes writer-ready required-item answer plan rows and preserves bounded judgment / counter-thesis material through rendering.

5. Updated Project OS ledgers, P33 source document, current context pack, root-cause ledger, capability ledger, execution plan ledger, checklist and README.

## Results

Single AI/Semis scoped memo projection replay passed:

- `renderer_projection.status=pass`
- `rendered_answer_chars=7136`
- `citation_label_count=22`
- `internal_marker_hits=[]`
- `final_verifier_projection.status=pass`
- `deterministic_status=pass`
- `projected_claim_count=8`
- `known_evidence_ref_count=17`
- `approx_total_prompt_chars_with_scaffold=17723`
- `workbench_projection.status=pass`
- Workbench projection rows: `7` sections, `6` claims, `5` gaps, `2` gates, `2` artifacts, `4` events

Multi-case Humanmade Gold Set readiness remains blocked:

- `case_count=15`
- `artifact_ready_count=1`
- `fresh_all_specialist_pass_count=0`
- `runtime_contract_ready_count=15`
- `blocking_case_count=15`

Interpretation: the single accepted AI/Semis memo artifact can now survive renderer / verifier / Workbench projection. That does not mean agent output is aligned with the full Humanmade Gold Set. The broader gold-set work still needs artifact-backed evidence-depth packs and fresh all-specialist gold passes case by case.

## Verification

Commands run:

```powershell
python -m py_compile src/sec_agent/langgraph_orchestrator.py src/sec_agent/p33_memo_projection_replay.py scripts/eval_multi_agent/run_p33_memo_projection_replay.py
python scripts/eval_multi_agent/run_p33_memo_projection_replay.py --strict
python -m pytest tests/test_p33_memo_projection_replay.py -q
python -m pytest tests/test_p33_memo_projection_replay.py tests/test_p33_memo_writer_node_runner.py tests/test_p33_humanmade_gold_set_runtime_quality_gate.py tests/test_multi_agent_memo_llm_repair.py -q
python -m pytest tests/test_multi_agent_contracts.py tests/test_memo_logic_plan.py -q
```

Observed results:

- `py_compile`: pass
- projection replay runner: single pass, multi-case blocked as expected
- focused projection tests: `3 passed`
- broader projection/writer tests: `98 passed`
- contract / memo logic tests: `55 passed`

## Boundaries

This is not:

- fresh all-specialist proof;
- accepted gold workpaper human review;
- real Workbench dogfood;
- broad full-chain pass;
- model comparison;
- release eval;
- multi-case Humanmade Gold Set pass.

Do not treat targeted specialist composite as fresh all-specialist output. Do not treat catalog / rubric / negative case definitions as runtime artifact depth. Do not run more paid Memo Writer or full-chain cases until the multi-case evidence-depth and specialist pass blockers are closed.

## Next

1. Build artifact-backed evidence-depth packs for the eight rubric cases and six negative cases.
2. Re-run AI/Semis as a fresh all-specialist gold pass, not just targeted composite.
3. For each gold case, verify Evidence Fusion -> Specialist -> Aggregate / JudgmentState -> MemoLogicPlan -> renderer / verifier / Workbench projection.
4. Only after those pass, consider scoped paid Memo Writer or model comparison.
