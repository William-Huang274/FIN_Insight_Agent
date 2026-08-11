# P30 Data / Script Quality Audit

Date: 2026-07-02

## Scope

User feedback clarified that poor full-chain output quality is not only a model or token-cost problem. If upstream project code, data scripts, artifact persistence, parser routes, or writer projection create the failure, the project must fix the earliest owned artifact instead of adding another gate or spending more DeepSeek tokens.

This entry records the deterministic data/script quality audit added before the next paid AI/Semis full-chain rerun.

## Implemented

- Added `src/sec_agent/data_script_quality_audit.py`.
  - Reads saved case artifacts only.
  - Does not call models, retrieval, web repair, or parsers.
  - Flags project-owned defects such as missing `memo_logic_plan.json`, evidence available but not rendered, deterministic salvage surfaces, product evidence not projected, display lineage gaps, parser/locator rows, and route-scope false gaps.
- Updated `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
  - Writes `data_script_quality_audit.json` and `data_script_quality_audit.md`.
  - Adds compact audit summary to `real_chain_eval_summary.json`.
  - Enforces `data_script_quality_gate` so owned data/script defects block full-chain pass.
- Updated `src/sec_agent/langgraph_orchestrator.py`.
  - Adds `memo_logic_plan` to artifact refs.
  - Preserves renderable draft/salvage memo surfaces when verifier status is fail, instead of replacing all content with one fixed `Bounded answer only` sentence.
- Added `tests/test_data_script_quality_audit.py`.
  - Bad artifact trace fails with root-cause candidates.
  - Complete trace passes.
  - Multi-agent artifact refs include `memo_logic_plan`.

## Existing Artifact Probe

Offline audit was run on:

`eval/sec_cases/outputs/p30_root_cause_repair_full_chain/20260702_p30_root_cause_repair_ai_semis_r2/real_chain_eval_summary.json`

No model call was made.

Result:

- `status=fail`
- failed cases:
  - `fin_deep_ai_infra_nvda_dell_capex_023`
  - `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025`
- issue counts:
  - `memo_logic_plan_artifact_missing=2`
  - `owned_parser_locator_gap_present=2`
  - `bounded_answer_salvage_surface=1`
  - `memo_writer_deterministic_salvage_used=1`
  - `product_evidence_available_not_rendered=1`
  - `required_item_available_not_rendered=1`
  - `source_route_scope_false_gap_present=1`

Interpretation:

- AI infra did not fail because public data was absent. It had required items with evidence available but not rendered.
- The one-line bounded answer is a writer / renderer salvage failure, not an acceptable investment memo.
- Missing `memo_logic_plan.json` makes the writer input unreplayable and blocks root-cause closeout.
- Semicap still has source-route / non-US disclosure parser rows that must be repaired or explicitly proven external.

## Verification

- `python -m pytest tests/test_data_script_quality_audit.py -q` -> `3 passed`
- `python -m pytest tests/test_agent_information_economy.py tests/test_multi_agent_real_llm_chain_eval.py::test_p30_required_item_gate_requires_summary_projection_for_answer_plan tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_flags_memo_logic_plan_validation_failure -q` -> `5 passed`
- `python -m compileall -q src/sec_agent/data_script_quality_audit.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py tests/test_data_script_quality_audit.py` -> pass
- `python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_renderer_preserves_renderable_salvage_memo_when_verifier_fails tests/test_data_script_quality_audit.py -q` -> `4 passed`
- `python -m compileall -q src/sec_agent/langgraph_orchestrator.py tests/test_multi_agent_memo_llm_repair.py` -> pass

## 2026-07-02 Root-Cause Repair Update

No paid model call was made.

Implemented repairs:

- `src/sec_agent/langgraph_orchestrator.py`
  - `memo_writer` now embeds the active `memo_logic_plan` into `memo_answer` when the writer output omits it.
  - `memo_logic_plan.json` persistence now recovers from `state.memo_logic_plan`, then `memo_answer.memo_logic_plan`, then a diagnostic `multi_agent_summary.memo_logic_plan` projection.
  - The persisted artifact records `artifact_persistence.source`, so future audits can distinguish state loss from standalone artifact persistence defects.
- `src/sec_agent/data_script_quality_audit.py`
  - Audit now distinguishes `memo_logic_plan_standalone_artifact_persistence` from `memo_logic_plan_generation_or_state_loss`.
  - Adds metrics for `memo_answer_embedded_memo_logic_plan_present` and `summary_memo_logic_plan_present`.
  - Source-route gap counting now treats `not_in_manifest_for_mcp_route_scope` as blocking only when unresolved. If the same ticker has a complete parser diagnosis with failure reason, parser status, and next parser action from targeted repair / official issuer rows, the route gap is counted as parser-boundary-diagnosed rather than unresolved source-route false gap.
- `src/sec_agent/memo_llm.py`
  - Deterministic memo salvage now consumes `memo_logic_plan.required_item_answer_plan`.
  - Required-item evidence is pulled into salvage claim selection before rendering.
  - Salvage generates dimension rows for required items, including bounded judgment, evidence bridge, counter-read, and financial bridge.
  - Product-spec / customer-deployment language no longer promotes architecture or deployment evidence into supplier revenue/order facts.

Deterministic verification:

- `python -m pytest tests/test_data_script_quality_audit.py -q` -> `7 passed`
- `python -m pytest tests/test_data_script_quality_audit.py -q` -> `8 passed` after adding an artifact-level full-chain-shaped proof case.
- `python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_salvage_uses_required_item_answer_plan_for_product_depth tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_salvages_repeated_length_failures_as_verifiable_memo tests/test_data_script_quality_audit.py -q` -> `8 passed`
- `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py::test_p30_required_item_gate_requires_summary_projection_for_answer_plan tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_flags_memo_logic_plan_validation_failure tests/test_agent_information_economy.py tests/test_multi_agent_output_quality_audit.py -q` -> `14 passed`
- `python -m pytest tests/test_sec_agent_mcp_runtime_tools.py::test_mcp_registry_uses_fpi_6k_as_interim_route_without_false_sec_gap tests/test_multi_agent_real_llm_chain_eval.py::test_p30_non_us_official_source_gap_requires_parser_diagnosis tests/test_multi_agent_real_llm_chain_eval.py::test_p30_non_us_official_source_gap_fails_without_parser_diagnosis tests/test_runtime_bridge_contracts.py::test_official_issuer_repair_materializes_asml_sec_context_without_promoting_exact_fact -q` -> `4 passed`
- `python -m compileall -q src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/data_script_quality_audit.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` -> pass
- Synthetic no-LLM P30 scorer probe for the AI infra required-item path:
  - `required_items_covered=true`
  - `required_item_answer_plan_present=true`
  - `required_item_answer_plan_projected_to_summary=true`
  - `economic_role_no_misuse=true`
  - status `pass`
  - Historical r2 artifacts still fail because the saved semicap artifact lacks the parser diagnosis; the new route-gap classifier does not hide that pre-repair sample.
- Synthetic full-chain-shaped artifact proof:
  - Test: `tests/test_data_script_quality_audit.py::test_data_script_quality_audit_passes_new_repaired_full_chain_artifact_shape`.
  - It uses the real `_write_memo_surface_artifacts` writer to persist `memo_logic_plan.json`, `memo_answer.json`, `claim_cards.json`, and rendered output, then runs `DataScriptQualityAudit` over the saved case directory.
  - Result: audit `status=pass`, `memo_answer_embedded_memo_logic_plan_present=true`, `summary_memo_logic_plan_present=true`, and ASML `not_in_manifest_for_mcp_route_scope` with complete parser diagnosis is not counted as unresolved route-scope false gap.
- Combined no-paid regression after specialist and Memo Writer input-pack fingerprint:
  - `python -m pytest ... -q` over data/script audit, writer repair, P30 source-route diagnosis, AIE, output-quality audit, and specialist fingerprint tests -> `30 passed`.
  - `python -m compileall -q ...` over touched runtime/eval/test files -> pass.
  - `git diff --check` over touched files -> pass; narrowed secret scan -> no matches.
- Latest extension: Memo Writer, Verifier, Research Lead, and Universe route results now carry digest-only `input_pack_fingerprint`; AIE surfaces lead / universe / Memo Writer / Verifier refs and approximate payload chars without storing prompt text.
- Latest current P30 no-paid regression after token-budget estimator v0.2 and upstream route fingerprints is `41 passed`.

Boundary:

- Historical r2 artifacts still fail offline audit because they were produced before these repairs.
- The synthetic artifact-level proof passes, but the next real generated full-chain artifact must still prove that `memo_logic_plan.json` exists, required items remain covered, and the data/script audit no longer reports the repaired defects under real runtime conditions.

## 2026-07-02 Stale State Root-Cause Repair Update

No paid model call was made.

Follow-up audit over the saved R13 semicap artifact found a different owned defect:

- The final `memo_answer` was `blocked_by_specialist_verification`.
- The active memo constraints still contained `unsupported_specialist_claims_without_supported_claims`.
- Upstream judgment state had already received pre-memo deterministic facts / claim material, so the blocker was stale rather than a true no-evidence condition.
- The writer route short-circuited on stale `specialist_verification` before it could use the current verified judgment plan.

Implemented repairs:

- `src/sec_agent/multi_agent_contracts.py`
  - `refresh_judgment_plan_after_governance_filter` now recomputes `memo_constraints` from the current supported / unsupported claim set.
  - `build_multi_agent_memo_draft` now treats stale verification blocks as stale only when the current judgment has verified supported claims and no current hard validation blocker.
  - Unsupported and provider-failed specialist claims are still excluded from memo claims; they are rendered as partial-scope caveats.
- `src/sec_agent/memo_llm.py`
  - `route_memo_writer_llm` no longer returns `blocked_by_specialist_verification` before asking the draft builder whether the current judgment is actually blocked.
- `src/sec_agent/langgraph_orchestrator.py`
  - Recomputes `specialist_verification` after pre-memo governance filtering, judgment refresh, and lead repair.
- `src/sec_agent/data_script_quality_audit.py`
  - Parser/locator gap detection now requires explicit parser / locator / adapter failure fields and no longer treats generic repair instructions containing "parser/source boundary" as a parser gap.
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - Economic-role misuse detection now distinguishes supplier revenue mapped to customer capex demand from issuer-own capex being misused as customer demand.

Deterministic verification:

- `python -m pytest tests/test_multi_agent_contracts.py::test_refresh_recomputes_stale_no_supported_claim_blocker_after_pre_memo_fact_injection tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_route_ignores_stale_verification_block_after_pre_memo_claim_refresh tests/test_multi_agent_judgment_memo_verifier.py::test_failed_specialist_is_rendered_as_partial_scope_caveat tests/test_d_series_fact_selection.py::test_pre_memo_fact_selection_adds_deterministic_claim_cards_for_approved_financial_facts -q` -> `4 passed`
- `python -m pytest tests/test_multi_agent_judgment_memo_verifier.py tests/test_d_series_fact_selection.py -q` -> `31 passed`
- `python -m pytest tests/test_data_script_quality_audit.py -q` -> `9 passed`
- `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_flags_economic_role_misuse tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_allows_capex_customer_demand_boundary_language tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_does_not_treat_supplier_revenue_to_customer_capex_as_own_capex -q` -> `3 passed`
- `python -m pytest tests/test_multi_agent_contracts.py -q` -> `37 passed`
- `python -m pytest tests/test_multi_agent_memo_llm_repair.py -q` -> `55 passed`
- `python -m pytest tests/test_multi_agent_langgraph_routing.py::test_multi_agent_graph_standard_path_runs_specialists tests/test_multi_agent_langgraph_routing.py::test_multi_agent_graph_blocks_unsupported_specialist_claims_before_memo_writer -q` -> `2 passed`

## Next

1. Prove the repaired `memo_logic_plan.json` persistence, refreshed `memo_constraints`, and refreshed `specialist_verification` on the next generated real-chain artifact.
2. Re-run data/script audit on the next generated artifact and confirm the repaired required-item projection no longer appears as `available_not_rendered`.
3. If semicap still exposes source-route / non-US disclosure parser rows after the stale-state fix, classify each row as parser/locator/adapter root cause versus real external source boundary before calling it an external data gap.
4. Only after the above pass should a single paid DeepSeek case be run.
