# 094 P33 Memo Writer Source Coverage And Surface Quality Repair

Date: 2026-07-06

## Scope

This worklog records the P33 single AI/Semis gold case node-level repair after aggregate r7. It does not record a paid Memo Writer rerun, full-chain run, model comparison, or accepted gold workpaper.

Current accepted upstream input:

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_node_result.json
```

## Problem

The previous paid DeepSeek Memo Writer artifact was manually weak even though it had passed earlier technical checks. It had shallow direct-answer density and template-like boundary language. Root-cause review found that the problem was not only the model:

- issuer/source coverage rows could be selected as main memo claims;
- dimension sections could use a source-coverage row as their primary thesis;
- salvage/action templates emitted generic low-density Chinese phrases;
- deep-research direct-answer length was not a hard verifier error.

The old paid artifact is now treated as invalid:

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_memo_writer_node_from_aggregate_r7_deepseek_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/memo_writer_node_result.json
```

Under the new verifier it fails with:

```json
{
  "status": "fail",
  "error_types": [
    "analyst_depth_generic_template_language",
    "analyst_depth_direct_answer_too_thin_for_profile"
  ]
}
```

## Root Cause

The earliest project-owned causes were:

1. `official_issuer_context` / `lead_targeted_repair_claim:issuer_official:*` rows were not separated from investable claims.
2. `_dimension_sections_from_claims()` used the first claim as primary without filtering source coverage.
3. Memo Writer claim selection did not penalize source coverage enough.
4. Chinese salvage/action templates generated generic phrases such as boundary-only continuation instructions.
5. The gap/boundary detector could overwrite bounded but decisionful long openings.

## Fix

Changed files:

```text
src/sec_agent/multi_agent_contracts.py
src/sec_agent/memo_llm.py
tests/test_multi_agent_contracts.py
tests/test_multi_agent_memo_llm_repair.py
```

Key changes:

- Source coverage claims are demoted to `evidence_summary_or_gap` with reason `source_coverage_context_not_main_claim`.
- Source coverage claims are excluded from dimension section grouping and cannot become the primary thesis.
- Memo claim selection and context priority penalize source coverage.
- Salvage/action text is dimension-specific and no longer emits low-density generic templates.
- Deep-research direct answers below the profile threshold hard-fail.
- Bounded but decisionful long openings are preserved rather than overwritten by salvage.

## Verification

Commands run:

```powershell
python -m py_compile src/sec_agent/memo_llm.py src/sec_agent/multi_agent_contracts.py
python -m pytest tests/test_multi_agent_contracts.py tests/test_multi_agent_memo_llm_repair.py -q
python -m pytest tests/test_p33_memo_writer_payload_preflight_runner.py tests/test_p33_memo_writer_node_runner.py -q
python scripts/eval_multi_agent/run_p33_memo_writer_payload_preflight_from_aggregate.py --aggregate-node-result eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_node_result.json --output-root eval/sec_cases/outputs/p33_gold_case_runs --run-id p33_stepwise_memo_writer_payload_preflight_source_coverage_hardening_20260706_r1 --strict
```

Observed:

- contract / memo repair suite: `129 passed`;
- P33 Memo Writer runner tests: `2 passed`;
- py_compile: pass;
- no-paid payload preflight: `gate_status=pass`;
- old weak paid memo now fails deterministic verifier.

Preflight artifact:

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_memo_writer_payload_preflight_source_coverage_hardening_20260706_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/memo_writer_payload_preflight_summary.json
```

Preflight summary:

- `compact_required_item_count=10`
- `compact_section_count=7`
- `compact_supported_claim_count=8`
- `approx_total_prompt_chars_with_scaffold=56016`
- selected source coverage claim count: `0`

## Boundary

- No paid Memo Writer rerun was executed.
- No full-chain run was executed.
- No model comparison was executed.
- No rendered gold workpaper was accepted.
- Prompt payload is still large at about `56k` chars, so payload compression remains open.

## Next

Allowed next actions:

1. If the user approves token spend, rerun only the Memo Writer node from accepted aggregate r7.
2. If avoiding token spend, continue no-paid writer payload compression / projection fixture work.

Disallowed next actions:

- broad full-chain;
- 20-50 case expansion;
- model comparison;
- using the old paid memo as a pass sample.
