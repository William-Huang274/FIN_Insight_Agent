# FIN 0.1.3 S3 — full-fragment Chat R2 relation-role failure

## Outcome

R2 ran on clean/synced commit `bffb6591...` and consumed four of six allowed DeepSeek calls with complete captures and zero retry. The thesis passed surface contract v1.1 and became the first accepted fragment. The mechanism then returned one bounded Tool Call but stopped at local validation with `finance_loop_micro_required_authority_missing`.

This is not a repeat of R1 and not a connectivity failure. The model used the earnings-call transcript as support, classified the broad 8-K as context, selected `CR::DELL::MULTI_DRIVER_CONTEXT`, and explicitly denied a product-to-segment/company allocation or causal bridge. The relation card nevertheless encoded both documents as mandatory support.

## Zero-call replay finding

Changing the 8-K role from context to support is not a valid fix. Replay exposed a second project defect immediately afterward: a non-thesis fragment was required to accept the thesis-level `supported` status, even though the mechanism itself selected `bounded_inference` and the terminal compiler already lowers the aggregate status conservatively.

The bounded repair is therefore one provider-neutral package:

1. separate relation-required support from optional context/counterevidence;
2. let each non-thesis fragment validate its own inference authority;
3. keep final status aggregation in the canonical terminal compiler;
4. replay the saved R2 Tool Calls, negative role mutations and a full fake sequence before any R3;
5. generate the next authority timestamp from the local clock rather than hand-entering it.

R2 authority, public result and raw captures remain immutable. Dynamic Research Truth Spine, five-unit execution, generalization and S3 acceptance remain false.

## Closure — relation-role contract v1.2

The provider-neutral successor closes both project defects without rewriting any R2 model text:

1. `CR::DELL::MULTI_DRIVER_CONTEXT` now requires only the Dell earnings-call transcript as supporting Evidence. The broad 8-K remains available as optional context and is not silently promoted to support.
2. Each non-thesis fragment validates the inference authority allowed by its own relation card. Global Judgment status, scope and causal authority are derived only after all fragments pass, by the canonical conservative terminal compiler.
3. The saved R2 thesis and mechanism Tool Calls both replay unchanged under v1.2. A mutation that supplies only contextual Evidence still fails with `finance_loop_micro_required_authority_missing`.
4. The compiled terminal remains conservative: `bounded_support / bounded_inference / multi_scope / multi_scope_financial / multi_driver_context_only`. The Harness did not generate or repair research prose.
5. Two fresh processes produced byte-equivalent proof output. Focused tests are `62 passed`; the full repository is `334 passed`; compileall, active-baseline verification (`127 Python / 8 frontend / 10 Runtime / 0 forbidden`) and secret scan (`6,637 / 0`) pass.

Formal evidence is recorded in:

- `configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_full_fragment_judgment_relation_role_zero_call_result_v1_2.json`
- `configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_full_fragment_judgment_relation_role_live_disposition_v1_2.json`
- `configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_full_fragment_judgment_relation_role_live_scope_decision_v1_2.json`

`RC-S3-018` is therefore closed at the relation-card／fragment-validation boundary. This engineering closure authorizes one fresh, clock-timestamped DELL `value_capture` FFJ-R3 only after clean push and Project OS preflight. It does not establish natural complete-Judgment L1, dynamic Agentic Research, five-unit execution, heterogeneous generalization, S3 acceptance, publication or release.
