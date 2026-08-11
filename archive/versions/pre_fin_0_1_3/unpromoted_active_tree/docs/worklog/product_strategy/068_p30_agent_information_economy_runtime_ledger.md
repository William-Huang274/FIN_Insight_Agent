# P30 Agent Information Economy Runtime Ledger

Date: 2026-07-02

## Scope

Continue the P30 self-audit under the new rule: owned upstream quality problems must be recorded and repaired, not hidden behind more gates or paid full-chain reruns.

This iteration implements the deterministic runtime ledger for `Agent Information Economy`. It treats token use as a product-quality signal: token spend must convert into role-specific evidence selection, accepted ClaimCards, Workpaper/JudgmentState material, and readable analyst judgment.

## Implemented

- Added `src/sec_agent/agent_information_economy.py`.
  - Builds `AgentInformationEconomyLedger` from saved eval summary and output-quality audit artifacts.
  - Adds preflight-only economy audit from `token_budget_plan`.
  - Flags high-token / low-yield cases, broad specialist fanout, invalid information-transfer proxy, duplicate evidence-ref transfer proxy, prompt-pack overlap proxy, and repair-loop agent-failure proxy.
  - Maps symptoms to root-cause candidate layers instead of treating them as output-only failures.
- Updated `src/sec_agent/specialist_llm.py`.
  - Specialist route summaries now include an `input_pack_fingerprint` with component digests, known evidence refs, row counts, and approximate payload chars.
  - It persists no raw prompt text; this is a traceability surface for prompt-overlap diagnosis, not a prompt dump.
  - `capital_macro_pack` prompt input is now role-projected instead of copied wholesale to multiple specialists: fundamental receives capital-structure sections, industry receives macro / exposure / vertical official sections, and risk receives debt / macro / rejected-risk sections.
- Updated `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
  - Writes `agent_information_economy_preflight.json` before any graph/model execution.
  - Writes `agent_information_economy_audit.json` and `.md` after output-quality audit.
  - Adds compact `agent_information_economy_audit` into aggregate eval summary for downstream Workbench / release gate usage.
  - Markdown now shows prompt evidence-ref overlap and same component digest counts per case.
- Added `tests/test_agent_information_economy.py`.
  - Healthy dense low-cost case passes.
  - High-token / low-claim-yield / broad-fanout case fails with root-cause candidates.
  - Expensive preflight plan fails before model calls.
- Updated real-chain preflight test to assert the new preflight economy artifact is written.
- Split specialist coverage and paid activation contracts.
  - `expected_specialist_agents` now remains the quality / dimension coverage expectation.
  - `expected_paid_specialist_agents` records which specialist LLM routes should actually be charged in the current run.
  - `expected_paid_specialist_priorities` records primary/supporting/conditional/low priority so token preflight can reflect role-specific input budgets.
  - AI/Semis deep-research catalog expansion keeps five quality specialists but drops non-material `market_valuation_analyst` from the paid activation expectation when the prompt does not ask for valuation, price-in, market reaction, liquidity, or short-interest analysis.
- Updated preflight/token-budget estimation and score route requirements to prefer `expected_paid_specialist_agents` while preserving the quality coverage list for audit.
- Updated preflight estimates so supporting specialists consume a supporting input package instead of primary-package token budgets. In the two AI/Semis cases, `risk_counterevidence_analyst` stays active but moves to supporting priority.
- Repaired deterministic runtime activation policy.
  - `market_snapshot` source availability now activates `market_operator` only.
  - `market_valuation_analyst` requires explicit market/valuation/price-in/stock-price intent.
  - This prevents source availability from becoming specialist fanout.
- Added deterministic data/script quality audit.
  - `src/sec_agent/data_script_quality_audit.py` reads saved full-chain case artifacts only; it does not call models, retrieval, web repair, or parsers.
  - `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` now writes `data_script_quality_audit.json/.md` and blocks aggregate pass with `data_script_quality_gate` when owned artifact defects are present.
  - `src/sec_agent/langgraph_orchestrator.py` now exposes `memo_logic_plan` in `artifact_refs`, so downstream audit can detect whether the plan is persisted and replayable.
  - Renderer no longer discards a renderable draft memo when verifier status is fail; if `direct_answer`, `memo_claims`, or dimension rows are present, it renders a bounded memo surface instead of replacing it with one fixed sentence.
  - Covered issues include `memo_logic_plan_artifact_missing`, `required_item_available_not_rendered`, `memo_writer_deterministic_salvage_used`, `product_evidence_available_not_rendered`, `display_value_lineage_missing`, `owned_parser_locator_gap_present`, and `source_route_scope_false_gap_present`.

## Boundaries

- No paid LLM call was made.
- This does not claim the AI/Semis full-chain cases are fixed.
- Current duplicate-context and invalid-transfer measurements are artifact-derived proxies. Exact prompt-token overlap needs prompt-pack capture.
- Prompt-pack overlap now has fingerprint-level capture for Research Lead, Universe, specialists, Memo Writer, and Verifier, but still does not persist full prompt text or exact prompt-token overlap.
- Workbench token-to-insight projection is implemented for saved AIE JSON artifacts; it is read-only and does not load raw prompt text.
- The two AI/Semis cases remain preflight-blocked until routing/compression/coalescing reduces token/call estimates or the user explicitly approves an expensive-run override.
- Data/script quality audit is now a hard pre-paid-rerun diagnostic. It can identify artifact and projection defects, but those defects still require root-cause repair in MemoLogicPlan persistence, writer projection, parser/route adapters, or Workbench projection.

## Verification

- `python -m pytest tests/test_agent_information_economy.py -q` -> `3 passed`
- `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_only_writes_plan_without_graph -q` -> `1 passed`
- `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_only_writes_plan_without_graph tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_blocks_expensive_paid_run tests/test_multi_agent_output_quality_audit.py::test_output_quality_audit_reports_cost_quality_metrics -q` -> `3 passed`
- `python -m pytest tests/test_multi_agent_output_quality_audit.py -q` -> `9 passed`
- `python -m compileall -q src/sec_agent/agent_information_economy.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` -> pass
- No-paid AI/Semis preflight:
  - Command: `python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --case-catalog-path tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json --case-id fin_deep_ai_infra_nvda_dell_capex_023 --case-id fin_deep_semicap_asml_amat_lrcx_klac_cycle_025 --token-budget-preflight-only --output-dir reports/r53_r60_p30_full_chain_ai_semis --run-id p30_aie_preflight_20260702`
  - Result: `blocked_preflight_token_budget`, `272000` estimated tokens, `18` estimated paid calls.
  - New ledger artifact: `reports/r53_r60_p30_full_chain_ai_semis/p30_aie_preflight_20260702/agent_information_economy_preflight.json`
  - Issue counts: `preflight_case_token_budget_high=2`, `preflight_paid_call_fanout_high=2`, `preflight_specialist_fanout_broad=2`.
  - Interpretation: both AI/Semis deep-research cases still assume five paid specialists plus Research Lead, Universe, Memo Writer, and Verifier. The next repair must reduce or coalesce activation from the planning layer; paid full-chain remains blocked.
- No-paid AI/Semis cost-aware preflight after pruning diagnostics:
  - Command: same two cases with `--run-id p30_aie_preflight_20260702b`.
  - Result: still `blocked_preflight_token_budget`, `272000` conservative estimated tokens and `18` conservative paid calls.
  - New diagnostic: `preflight_specialist_pruning_available=2`; both cases identify `market_valuation_analyst` as prunable under required-item cost-aware estimation.
  - After advisory specialist pruning, each case drops from `136000` / `9` calls to `124000` / `8` calls. This is still above the `120000` per-case token budget and the two-case run still exceeds the `180000` run budget.
  - Interpretation: pruning broad market specialist fanout is necessary but insufficient. Next repair should compress/coalesce `memo_writer`, `universe_relationship`, and role-specific specialist inputs before paid rerun.
- Contract-aligned no-paid AI/Semis preflight:
  - Command: same two cases with `--run-id p30_aie_preflight_20260702c`.
  - Result: `blocked_preflight_token_budget`, now `248000` estimated tokens and `16` estimated paid calls.
  - Each case now estimates `124000` tokens / `8` paid calls: Research Lead, Universe, four paid specialists, Memo Writer, and Verifier.
  - The remaining blocker is no longer the fifth market specialist. It is payload and orchestration cost across `universe_relationship`, role-specific specialist input packs, `memo_writer`, and verifier.
- Priority-aligned no-paid AI/Semis preflight:
  - Command: same two cases with `--run-id p30_aie_preflight_20260702e`.
  - Result: still `blocked_preflight_token_budget` at the run level, now `239200` estimated tokens and `16` paid calls.
  - Each case now estimates `119600` tokens / `8` paid calls and has no case-level token-budget violation.
  - `AgentInformationEconomyLedger` now reports each case as `pass`; run-level fail is only because two deep cases together exceed `180000` total budget and `8` paid-call cap.
- Single-case no-paid preflight:
  - Command: `fin_deep_ai_infra_nvda_dell_capex_023` only with `--run-id p30_aie_single_preflight_20260702a`.
  - Result: `allowed`, `119600` estimated tokens, `8` paid calls, no violations, AIE preflight `pass`.
  - Interpretation: the next paid DeepSeek test should be one deep case only, after confirming runtime activation follows the paid specialist contract.
- Role-projected budget estimator v0.2:
  - `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` now marks token-budget plans with `estimate_policy=role_projected_compact_prompt_budget_v0_2`.
  - The estimator reflects role-specific specialist pack projection and the Memo Writer `writer_thesis_skeleton_first_compact_verified_inputs` contract instead of the older static upper bound.
  - Single AI infra no-paid preflight `p30_aie_single_preflight_v0_2_20260702`: `allowed`, `101400` estimated tokens, `8` paid calls.
  - Two AI/Semis no-paid preflight `p30_aie_two_case_preflight_v0_2_20260702`: still `blocked_preflight_token_budget`, `202800` estimated tokens, `16` paid calls. The blocker is now run-level total and paid-call count, not per-case budget.
  - This is still a preflight estimate, not an actual token meter; real run audit must compare estimated vs actual prompt/token usage after a valid single-case run.
- Deterministic runtime activation audit:
  - The two real AI/Semis catalog cases now route to the same four active specialists in `expected_paid_specialist_agents`: `fundamental_analyst`, `product_technology_analyst`, `industry_supply_chain_analyst`, and `risk_counterevidence_analyst`.
  - `market_valuation_analyst` is no longer activated by `market_snapshot` source tier alone.
  - `risk_counterevidence_analyst` is `supporting` priority in both cases.
- Specialist input-pack fingerprint / prompt-overlap audit:
  - `src/sec_agent/specialist_llm.py` now adds `input_pack_fingerprint` to `specialist_route_results`.
  - `src/sec_agent/agent_information_economy.py` consumes those fingerprints and emits `prompt_pack_overlap_proxy` plus `specialist_input_pack_deduplication_or_coalescing` root-cause candidates when multiple specialists receive identical component digests or high shared evidence-ref overlap.
  - `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` markdown reports prompt ref overlap and same pack digest counts.
  - Tests: `python -m pytest tests/test_agent_information_economy.py tests/test_multi_agent_specialist_llm.py::test_specialist_env_router_runs_active_specialists_with_bounded_state tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_only_writes_plan_without_graph tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_uses_expected_paid_specialists tests/test_multi_agent_output_quality_audit.py -q` -> `16 passed`.
- Role-projected capital/macro prompt pack:
  - `capital_macro_pack` no longer sends identical section payloads to fundamental / industry / risk specialists.
  - New deterministic regression: `tests/test_multi_agent_specialist_llm.py::test_capital_macro_pack_prompt_is_role_projected_not_duplicated_wholesale`.
  - Targeted no-paid regression after this repair: `31 passed`.
- Stale verification / stale constraint root-cause repair:
  - Real semicap R13 artifacts showed the writer was blocked by an old `unsupported_specialist_claims_without_supported_claims` constraint even after pre-memo deterministic facts and ClaimCards were available upstream.
  - `refresh_judgment_plan_after_governance_filter` now recomputes `memo_constraints` from the current supported / unsupported claim set instead of carrying stale blocker reasons forward.
  - `langgraph_orchestrator` now re-runs `verify_specialist_outputs_for_memo` after governance filtering, lead repair, and judgment refresh, so `specialist_verification` and `verified_judgment_plan` stay synchronized.
  - `build_multi_agent_memo_draft` and `route_memo_writer_llm` now distinguish a stale verification block from a current unsafe judgment. Unsupported/provider-failed specialist claims remain excluded, but verified current claims are no longer discarded.
  - This is a state-consistency root fix, not a fallback: provider/runtime specialist failures are exposed as partial-scope caveats while verified claims remain usable.
- Memo Writer input-pack fingerprint:
  - `src/sec_agent/memo_llm.py` now records `memo_route_result.input_pack_fingerprint` for pass, deterministic salvage, and specialist-verification blocked paths.
  - The fingerprint is digest-only: component digests, item counts, evidence-ref counts, approximate payload chars, memo profile, response language, and known evidence refs. It does not persist full prompt text or prose.
  - `src/sec_agent/agent_information_economy.py` now exposes `information_transfer.memo_writer_input_pack`, including largest input components, known evidence-ref count, and approximate payload chars.
  - `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` now shows `Memo refs` and `Memo payload chars` in the AIE markdown table.
  - New deterministic regressions: `tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_route_records_input_pack_fingerprint_without_prompt_text` and `tests/test_agent_information_economy.py::test_agent_information_economy_reads_memo_writer_input_fingerprint`.
  - Targeted no-paid regression after this repair: `33 passed`.
- Verifier input-pack fingerprint:
  - `src/sec_agent/memo_llm.py` now records `verifier_input_pack_fingerprint` and embeds the same digest-only record inside `claim_verification.verifier_input_projection.input_pack_fingerprint`.
  - The fingerprint proves Verifier only received final memo / referenced ClaimCard projection, allowed refs, source-boundary notes, and deterministic verification summary; it does not persist full prompt text.
  - `src/sec_agent/agent_information_economy.py` now exposes `information_transfer.verifier_input_pack`, and AIE markdown adds `Verifier refs` / `Verifier payload chars`.
  - New deterministic regressions: `tests/test_multi_agent_memo_llm_repair.py::test_verifier_route_records_input_pack_fingerprint_without_prompt_text` and `tests/test_agent_information_economy.py::test_agent_information_economy_reads_verifier_input_fingerprint`.
- Research Lead / Universe input-pack fingerprint:
  - `src/sec_agent/research_lead_llm.py` now records digest-only `input_pack_fingerprint` from request scope, source inventory, context, loop budget, registry, and route-choice policy.
  - `src/sec_agent/universe_relationship_llm.py` now records digest-only `input_pack_fingerprint` from activation plan, compact relationship lookup prompt view, known relationship refs, and source-inventory summary.
  - `src/sec_agent/langgraph_orchestrator.py` persists both fingerprints into state and `llm_routes`; `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` carries them into `agent_audit`.
  - `src/sec_agent/agent_information_economy.py` now exposes `information_transfer.research_lead_input_pack` and `information_transfer.universe_relationship_input_pack`; AIE markdown adds lead/universe ref counts and payload chars.
  - New deterministic regressions: `tests/test_multi_agent_research_lead_llm.py::test_research_lead_route_records_input_pack_fingerprint_without_prompt_text`, `tests/test_multi_agent_universe_relationship_llm.py::test_universe_relationship_route_records_input_pack_fingerprint_without_prompt_text`, and `tests/test_agent_information_economy.py::test_agent_information_economy_reads_research_lead_and_universe_input_fingerprints`.
- Current combined no-paid P30 regression:
  - `python -m pytest ... -q` over data/script audit, writer/verifier repair/fingerprint, Research Lead/Universe fingerprint, token-budget v0.2, P30 source-route diagnosis, AIE, output-quality audit, and specialist role projection -> `41 passed`.
- Current no-paid stale-state/root-cause regression after this update:
  - `python -m pytest tests/test_multi_agent_contracts.py::test_refresh_recomputes_stale_no_supported_claim_blocker_after_pre_memo_fact_injection tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_route_ignores_stale_verification_block_after_pre_memo_claim_refresh tests/test_multi_agent_judgment_memo_verifier.py::test_failed_specialist_is_rendered_as_partial_scope_caveat tests/test_d_series_fact_selection.py::test_pre_memo_fact_selection_adds_deterministic_claim_cards_for_approved_financial_facts -q` -> `4 passed`.
  - `python -m pytest tests/test_multi_agent_judgment_memo_verifier.py tests/test_d_series_fact_selection.py -q` -> `31 passed`.
  - `python -m pytest tests/test_data_script_quality_audit.py -q` -> `9 passed`.
  - `python -m pytest tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_flags_economic_role_misuse tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_allows_capex_customer_demand_boundary_language tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_does_not_treat_supplier_revenue_to_customer_capex_as_own_capex -q` -> `3 passed`.
  - `python -m pytest tests/test_multi_agent_contracts.py -q` -> `37 passed`.
  - `python -m pytest tests/test_multi_agent_memo_llm_repair.py -q` -> `55 passed`.
  - `python -m pytest tests/test_multi_agent_langgraph_routing.py::test_multi_agent_graph_standard_path_runs_specialists tests/test_multi_agent_langgraph_routing.py::test_multi_agent_graph_blocks_unsupported_specialist_claims_before_memo_writer -q` -> `2 passed`.
- Workbench full-chain budget hardening:
  - `src/sec_agent/workbench/job_runner.py` now passes explicit `--token-budget-total 180000`, `--token-budget-per-case 120000`, and `--max-paid-calls 8` to every Workbench full-chain eval runner that uses `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
  - Workbench does not add `--allow-expensive-llm` by default. Expensive runs must be intentionally reviewed and launched outside the default product runner.
  - Deterministic API tests prove G11, diagnostic probe, and catalog-subset eval runners carry the budget arguments and do not pass secrets through command args.
  - No-paid preflight `p30_workbench_budget_preflight_gate_20260703` over the two AI/Semis deep cases remains blocked before graph/model execution: `202800` estimated tokens, `16` paid calls, run-level token and paid-call violations.
  - No-paid preflight `p30_workbench_budget_single_case_preflight_20260703` over the single AI infra case is allowed: `101400` estimated tokens, `8` paid calls.
  - Interpretation: the product runner now enforces the same information-economy boundary as the CLI. The next paid test, if approved, must be one deep case first; two-case/broader regression remains blocked until further input coalescing or budget review.
- Workbench token-to-insight projection:
  - Added `src/sec_agent/workbench/agent_information_economy_projection.py`.
  - Added `GET /api/evals/agent-information-economy` to the Workbench backend.
  - The projection scans compact `agent_information_economy_preflight.json` / `agent_information_economy_audit.json` artifacts under the known eval/report output roots, returns latest run status, budget-block count, max estimated tokens / paid calls, issue counts, artifact refs, and compact case token plans.
  - Added a Workbench frontend `Agent Information Economy` panel in the eval area and R53-R60 Ops surface. It shows whether the latest AIE artifact is pass/fail, which run is latest, whether budget preflight blocked, and where the compact artifact lives.
  - Verification: backend API contract test passes, `tsc` passes, Vite production build passes, and live projection over existing artifacts reports latest single-case preflight as pass while retaining historical max two-case budget pressure (`202800` tokens / `16` paid calls).
- Token-budget scheduler advice:
  - `token_budget_plan.json` now includes `scheduler_advice`, distinguishing `case_budget_repair_required` from `split_required`.
  - `AgentInformationEconomyLedger` carries the same scheduler advice into `agent_information_economy_preflight.json`, and the Workbench projection/UI preserves it.
  - No-paid preflight `p30_scheduler_advice_preflight_20260703b` confirms the two AI/Semis deep cases are not case-level over budget; they are a batch-level problem and must be run as two separate paid batches of one case each (`101400` tokens / `8` paid calls per batch).
  - Verification: token-budget scheduler regression, AIE preflight regression, Workbench projection regression, TypeScript, Vite build, compileall, and `git diff --check` all pass.
- ProductIntelligenceGraph -> ClaimCards root-cause repair:
  - Earlier deterministic mock artifacts proved `ProductIntelligenceGraph` / `ProductEvidencePack` / `CustomerDeployment` / `ProductRelationshipGraph` rows existed in `supervising_analyst_pack`, but `verified_judgment_plan` still carried only six AMZN/MSFT/GOOGL targeted-repair ClaimCards. Product evidence was available upstream but not converted into memo-ready ClaimCard authority for NVDA/DELL product capability, deployment, DELL product/business KPI, or NVDA->DELL component read-through.
  - `src/sec_agent/langgraph_orchestrator.py` now converts bounded product bridge packs into `supervising_analyst` ClaimCards before MemoLogicPlan / JudgmentState closeout: `company_reported_product_operating_fact`, `product_intelligence_graph_bounded_claim`, `customer_deployment_bounded_signal`, and `product_relationship_graph_bounded_claim`.
  - The converter preserves authority boundaries. Product/spec/deployment/relationship rows can support bounded product capability, adoption, channel, supply-chain, or competitive-context judgment; they cannot be promoted to SKU revenue, shipments, ASP, sell-through, backlog, market share, customer order value, or direct win/loss without separate exact rows.
  - `refresh_judgment_plan_after_governance_filter` now refreshes `supported_claims` after thesis synthesis, so synthesized thesis ClaimCards are not only present in derived packs but also in the ClaimCard main table.
  - Product technology is now a valid business slot for thesis synthesis. AI/Semis cases can synthesize thesis from financial + product evidence rather than requiring product evidence to masquerade as financial facts.
  - Runtime memo-slot normalization no longer defaults unknown slots to `thesis`. It maps runtime aliases such as `industry_supply_chain`, `competition_market`, and `capital_allocation` to stable memo slots, and sends unknown slots to `evidence_gap` instead of silently polluting thesis.
  - No-paid runtime proof `p30_mock_product_bridge_slot_alias_fix_20260703` over `fin_deep_ai_infra_nvda_dell_capex_023`: `verified_judgment_plan.supported_claim_count=14`, `memo_claim_count=14`, supported slots are `thesis/product_technology/fundamentals/industry_relationship`, `p30_root_cause_quality_audit.status=pass/root_cause_rows=[]`, and `agent_information_economy_audit.status=pass/issues=[]`. The run remains diagnostic-only because mock backend intentionally has no paid LLM, real retrieval, or real specialist quality.
- Product bridge / AIE root-cause regression:
  - `python -m pytest tests/test_multi_agent_contracts.py::test_thesis_synthesis_uses_product_technology_as_business_slot tests/test_multi_agent_memo_llm_repair.py::test_product_bridge_pack_is_converted_to_bounded_claim_cards tests/test_multi_agent_memo_llm_repair.py::test_product_bridge_claims_refresh_into_thesis_and_dimension_plan tests/test_agent_information_economy.py::test_agent_information_economy_fails_high_cost_low_yield_fanout tests/test_agent_information_economy.py::test_agent_information_economy_allows_four_specialists_when_claim_yield_is_healthy -q` -> `5 passed`.
  - `python -m pytest tests/test_multi_agent_contracts.py::test_runtime_memo_slot_aliases_do_not_default_to_thesis tests/test_multi_agent_contracts.py::test_thesis_synthesis_uses_product_technology_as_business_slot tests/test_multi_agent_memo_llm_repair.py::test_product_bridge_pack_is_converted_to_bounded_claim_cards tests/test_multi_agent_memo_llm_repair.py::test_product_bridge_claims_refresh_into_thesis_and_dimension_plan -q` -> `4 passed`.
  - `python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_renderer_projects_required_item_answers_from_product_graph_pack tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_runtime_required_agents_use_expected_paid_specialists tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_initial_state_forces_catalog_execution_mode tests/test_agent_information_economy.py::test_preflight_information_economy_flags_expensive_fanout_before_model_calls tests/test_agent_information_economy.py::test_agent_information_economy_allows_four_specialists_when_claim_yield_is_healthy tests/test_multi_agent_contracts.py::test_thesis_synthesis_uses_product_technology_as_business_slot -q` -> `6 passed`.
  - `python -m pytest tests/test_agent_information_economy.py tests/test_multi_agent_contracts.py::test_thesis_driver_pack_structures_verified_claims_for_memo_surface tests/test_multi_agent_contracts.py::test_thesis_driver_pack_preserves_non_financial_signal_authority_fields -q` -> `10 passed`.
  - `python -m compileall -q src/sec_agent/langgraph_orchestrator.py src/sec_agent/multi_agent_contracts.py src/sec_agent/agent_information_economy.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` -> pass.
- Required-item boundary projection repair:
  - New semicap mock artifact `p30_mock_semicap_source_route_state_refresh_20260703` showed the remaining P30 root-cause row was `export_restriction_context`: `MemoLogicPlan.required_item_answer_plan` contained the required item, but no promoted ClaimCard/source row or typed gap carried export / China / license evidence into the final memo.
  - `src/sec_agent/langgraph_orchestrator.py` now projects required items without matching promoted evidence as explicit boundary rows instead of silently omitting them. The renderer writes a required-question coverage line with `answer_status=answered_with_boundary_no_promotable_evidence`, no fabricated citation, and a concrete missing-source description.
  - Semicap-specific required item language was added for `asml_orders_or_backlog`, `shipment_or_cycle_context`, `customer_concentration_or_deployment`, and `export_restriction_context`. The export-control item now states that China/export restriction/license is a required risk item, identifies the missing official risk / regional exposure / license / order-cancellation evidence, and limits the conclusion to directional risk rather than quantified revenue impact.
  - No-paid rerun `p30_mock_semicap_required_boundary_projection_20260703` over `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025` now has `p30_root_cause_quality_audit.status=pass`, `root_cause_rows=[]`, and all four semicap required items `covered`. Overall runner `gate_status=fail` remains expected because mock backend does not invoke real Research Lead, Universe, retrieval, specialists, Memo Writer, or Verifier.
  - Regression: `python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_renderer_projects_required_item_boundary_when_no_promotable_evidence tests/test_multi_agent_memo_llm_repair.py::test_renderer_projects_required_item_answers_from_product_graph_pack tests/test_multi_agent_memo_llm_repair.py::test_product_bridge_pack_is_converted_to_bounded_claim_cards tests/test_multi_agent_memo_llm_repair.py::test_product_bridge_claims_refresh_into_thesis_and_dimension_plan tests/test_multi_agent_real_llm_chain_eval.py::test_p30_required_item_gate_requires_summary_projection_for_answer_plan tests/test_multi_agent_contracts.py::test_runtime_memo_slot_aliases_do_not_default_to_thesis -q` -> `6 passed`; `python -m compileall -q src/sec_agent/langgraph_orchestrator.py tests/test_multi_agent_memo_llm_repair.py` -> pass.
- Earlier combined no-paid repair regression before capital/macro role projection:
  - `python -m pytest tests/test_data_script_quality_audit.py tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_salvage_uses_required_item_answer_plan_for_product_depth tests/test_multi_agent_memo_llm_repair.py::test_renderer_preserves_renderable_salvage_memo_when_verifier_fails tests/test_multi_agent_real_llm_chain_eval.py::test_p30_required_item_gate_requires_summary_projection_for_answer_plan tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_flags_memo_logic_plan_validation_failure tests/test_multi_agent_real_llm_chain_eval.py::test_p30_non_us_official_source_gap_requires_parser_diagnosis tests/test_multi_agent_real_llm_chain_eval.py::test_p30_non_us_official_source_gap_fails_without_parser_diagnosis tests/test_sec_agent_mcp_runtime_tools.py::test_mcp_registry_uses_fpi_6k_as_interim_route_without_false_sec_gap tests/test_runtime_bridge_contracts.py::test_official_issuer_repair_materializes_asml_sec_context_without_promoting_exact_fact tests/test_agent_information_economy.py tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_specialist_llm.py::test_specialist_env_router_runs_active_specialists_with_bounded_state -q` -> `30 passed`.
  - `python -m compileall -q ...` over touched runtime/eval/test files -> pass.
  - `git diff --check` over touched files -> pass; narrowed secret scan -> no matches.
- `python -m pytest tests/test_agent_information_economy.py tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_real_llm_chain_eval.py::test_multi_agent_real_llm_chain_dry_run_resolves_catalog_subset tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_uses_expected_paid_specialists tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_only_writes_plan_without_graph tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_blocks_expensive_paid_run -q` -> `16 passed`
- `python -m pytest tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_research_lead_llm.py tests/test_agent_information_economy.py tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_real_llm_chain_eval.py::test_multi_agent_real_llm_chain_dry_run_resolves_catalog_subset tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_uses_expected_paid_specialists tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_only_writes_plan_without_graph tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_blocks_expensive_paid_run -q` -> `53 passed`
- Data/script quality deterministic audit:
  - `python -m pytest tests/test_data_script_quality_audit.py -q` -> `3 passed`
  - `python -m pytest tests/test_agent_information_economy.py tests/test_multi_agent_real_llm_chain_eval.py::test_p30_required_item_gate_requires_summary_projection_for_answer_plan tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_flags_memo_logic_plan_validation_failure -q` -> `5 passed`
  - `python -m compileall -q src/sec_agent/data_script_quality_audit.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py tests/test_data_script_quality_audit.py` -> pass
  - `python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_renderer_preserves_renderable_salvage_memo_when_verifier_fails tests/test_data_script_quality_audit.py -q` -> `4 passed`
  - `python -m compileall -q src/sec_agent/langgraph_orchestrator.py tests/test_multi_agent_memo_llm_repair.py` -> pass
- Offline probe over existing P30 r2 artifacts, no model call:
  - Input: `eval/sec_cases/outputs/p30_root_cause_repair_full_chain/20260702_p30_root_cause_repair_ai_semis_r2/real_chain_eval_summary.json`
  - Output probe: `data_script_quality_audit.offline_probe.json/.md` under the same eval output directory.
  - Result: `status=fail`; failed cases are `fin_deep_ai_infra_nvda_dell_capex_023` and `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025`.
  - Issue counts: `memo_logic_plan_artifact_missing=2`, `owned_parser_locator_gap_present=2`, `bounded_answer_salvage_surface=1`, `memo_writer_deterministic_salvage_used=1`, `product_evidence_available_not_rendered=1`, `required_item_available_not_rendered=1`, `source_route_scope_false_gap_present=1`.
  - Interpretation: AI infra has four required items with evidence available but not rendered; semicap still has route-scope / non-US parser root-cause rows. These are owned repair items, not public-source absence.
- Data/script root-cause deterministic repair:
  - `memo_logic_plan` is now embedded into `memo_answer` and persisted with artifact source lineage.
  - `DataScriptQualityAudit` now separates standalone artifact persistence defects from plan generation/state-loss defects.
  - `DataScriptQualityAudit` now counts source-route false gaps only when unresolved; ASML/FPI `not_in_manifest_for_mcp_route_scope` rows with complete targeted-repair parser diagnosis are treated as diagnosed parser-boundary rows, not hidden source absence.
  - Deterministic memo salvage consumes `memo_logic_plan.required_item_answer_plan` and emits required-item dimension rows instead of only ClaimCard summary prose.
  - Product spec / architecture and customer deployment salvage text no longer promotes non-revenue evidence into supplier revenue/order facts.
  - P30 root-cause audit no longer misclassifies generic repair text mentioning parser/source boundary as `owned_parser_locator_gap_present`; only explicit parser / locator / adapter failure fields count.
  - Economic-role audit no longer treats supplier revenue mapped to customer capex demand as issuer-own capex misuse unless the local text explicitly says the focus issuer's own capex is customer demand.
  - Semicap R13 root cause was narrowed from public-source absence to runtime state drift: supported claims / dimension analyses existed upstream, but stale `memo_constraints` and stale `specialist_verification` forced a one-line blocked memo.
  - Verification: targeted writer/data/P30/AIE regressions passed (`8 passed`, `8 passed`, `14 passed`), ASML/FPI route/parser diagnosis tests passed (`4 passed`), and the no-LLM synthetic AI infra P30 scorer passes all required-item and economic-role checks.
  - Synthetic full-chain-shaped artifact proof now uses the real artifact writer to persist `memo_logic_plan.json`, `memo_answer.json`, `claim_cards.json`, and rendered output before `DataScriptQualityAudit` reads the saved directory; it passes with embedded plan, summary plan, required-item coverage, and ASML route-gap diagnosis preserved.

## 2026-07-03 Input-Pack Fingerprint Projection / False-Positive Duplicate Repair

This update closes a root-cause observability defect in the no-paid / deterministic path before any new paid DeepSeek run.

- Mock specialist routes now project role-specific `input_pack_fingerprint` records through `_with_projected_specialist_input_pack(...)` in `src/sec_agent/langgraph_orchestrator.py`.
  - This uses the same shared specialist context / specialist request shape as the runtime route.
  - The persisted record is digest-only and carries `capture_source=deterministic_mock_projected_specialist_request`.
  - It does not save raw prompt text or full messages.
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` now synthesizes deterministic fallback fingerprints for Research Lead, Universe Relationship, Memo Writer, Verifier, and specialist route rows when a saved/mock artifact lacks native route fingerprints.
  - Memo Writer fallback first reuses the real memo writer input-pack contract.
  - Verifier fallback first reuses the real verifier projection contract.
  - Universe fallback first reuses the real universe relationship lookup prompt-view contract.
  - If a private contract import changes, the fallback records the contract error in the fingerprint instead of silently hiding it.
- AIE duplicate-evidence transfer no longer treats generic nested `source_id` fields as evidence refs.
  - The previous `supplier_customer_official_news` duplicate was a source-role / source-id false positive, not duplicate evidence transmission.
  - `src/sec_agent/agent_information_economy.py` and the eval fallback scanner now count only evidence-like refs such as `evidence_ref`, `evidence_id`, `source_fact_id`, `raw_record_ref`, and explicit evidence-ref arrays.
- AIE now reads both `fingerprint_policy` and older `policy` fields from input-pack fingerprints.

Latest no-paid proof:

- Run artifact: `reports/r53_r60_p30_full_chain_ai_semis/p30_mock_semicap_aie_input_fingerprint_projection_20260703_r4/`.
- AIE result: `agent_information_economy_audit.status=pass`, `issue_counts={}`.
- Specialist activation: `4` active specialists with role-specific input rows:
  - `fundamental_analyst=5`
  - `product_technology_analyst=48`
  - `industry_supply_chain_analyst=48`
  - `risk_counterevidence_analyst=10`
- Input-pack payload diagnostics are now visible:
  - Research Lead: `0` known refs, about `16,469` prompt chars, `capture_source=deterministic_fallback_from_saved_research_lead_state`.
  - Universe Relationship: `2` known refs, about `5,930` prompt chars, `capture_source=deterministic_fallback_using_universe_relationship_input_contract`.
  - Memo Writer: `26` known refs, about `71,963` prompt chars, `capture_source=deterministic_fallback_using_memo_writer_input_contract`.
  - Verifier: `51` known refs, about `34,636` prompt chars, `capture_source=deterministic_fallback_using_verifier_projection_contract`.
- Prompt overlap is measurable but not blocking in this run:
  - `same_component_digest_count=0`
  - `duplicate_prompt_evidence_ref_count=5`
  - `overlap_detected=false`
- Overall eval summary remains `diagnostic_only=true` and `gate_status=fail` because this mock run intentionally does not invoke real Research Lead, retrieval, specialists, Memo Writer, or Verifier. This is not a paid full-chain product-quality closeout.

Focused no-paid verification:

```powershell
python -m compileall -q src/sec_agent/langgraph_orchestrator.py src/sec_agent/agent_information_economy.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_memo_llm_repair.py
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_mock_specialist_route_projects_role_specific_input_fingerprint tests/test_multi_agent_real_llm_chain_eval.py::test_agent_audit_projects_input_fingerprints_for_deterministic_routes tests/test_agent_information_economy.py::test_agent_information_economy_flags_prompt_pack_overlap_from_fingerprints tests/test_agent_information_economy.py::test_agent_information_economy_reads_memo_writer_input_fingerprint tests/test_agent_information_economy.py::test_agent_information_economy_reads_research_lead_and_universe_input_fingerprints tests/test_agent_information_economy.py::test_agent_information_economy_reads_verifier_input_fingerprint -q
```

Result: `6 passed`.

## 2026-07-03 Memo / Verifier Payload Coalescing

This update addresses the next AIE finding from the same no-paid artifact: some compact prompt views were still carrying duplicate planning / memo views.

Root cause:

- `MemoLogicPlan.writer_thesis_skeleton.dimension_moves` repeated detailed `required_item_answer_moves` that were already present in `required_item_answer_plan`.
- Verifier projection passed both `memo_answer.memo_claims` and duplicate `memo_answer.supported_claims` when deterministic / salvage surfaces kept both fields.
- Compact ClaimCards still included rank metadata and long role text that are useful for selection, but not for the writer after selection has already happened.

Repair:

- `src/sec_agent/memo_llm.py` now keeps only `required_item_answer_move_count` inside writer thesis skeleton. Detailed prompts remain in `required_item_answer_plan`, the single source of truth for required-item writing.
- `_compact_memo_for_verifier(...)` no longer repeats `supported_claims` when `memo_claims` are present. Verifier still receives `memo_claim_ref_inventory` and `allowed_evidence_refs`, so evidence checking remains intact.
- `_compact_claim_card(...)` trims writer-facing ClaimCard text and removes rank-only fields from the writer payload while preserving claim id, role/economic boundary, evidence refs, source families, parser diagnosis when present, and analyst-depth bridge fields.

Focused verification:

```powershell
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_memo_logic_plan_compaction_does_not_duplicate_required_item_prompts tests/test_multi_agent_memo_llm_repair.py::test_verifier_projection_does_not_duplicate_memo_supported_claims_when_memo_claims_exist tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_route_records_input_pack_fingerprint_without_prompt_text tests/test_agent_information_economy.py::test_agent_information_economy_reads_memo_writer_input_fingerprint tests/test_agent_information_economy.py::test_agent_information_economy_reads_verifier_input_fingerprint -q
```

Result: `5 passed`.

No-paid runtime proof:

- Run artifact: `reports/r53_r60_p30_full_chain_ai_semis/p30_mock_semicap_aie_payload_coalescing_20260703/`.
- AIE result: `status=pass`, `issue_counts={}`.
- Data/script audit: `status=pass`, `issue_counts={}`.
- Payload change versus the previous semicap no-paid AIE run:
  - Memo Writer payload: `71,963 -> 68,383` approximate chars.
  - MemoLogicPlan component: `32,190 -> 29,662` approximate chars.
  - Verifier payload: `34,636 -> 27,445` approximate chars.
  - Verifier memo-answer component: `25,326 -> 18,135` approximate chars.
- Prompt overlap remains non-blocking:
  - `same_component_digest_count=0`
  - `duplicate_prompt_evidence_ref_count=5`
  - `overlap_detected=false`

Boundary:

- This is a real information-transfer root-cause repair, but still a no-paid mock diagnostic run.
- The overall eval summary remains `diagnostic_only=true` and `gate_status=fail` because mock backend intentionally skips real Research Lead, retrieval, specialists, Memo Writer, and Verifier.
- Paid single-case rerun remains gated by data/script quality, AIE preflight, and exact case-level token budget review.

Next root-cause targets before any paid broad eval:

- Continue reducing large memo-side payloads where AIE proves duplicate or low-value transfer remains, especially `supported_claims` versus thesis/driver projections.
- Keep full-chain paid runs blocked until data/script quality, AIE preflight, and required-item coverage gates pass on the exact case to be tested.

## 2026-07-03 Specialist Prompt Row Projection / AIE Measurement Boundary Repair

This update continues the no-paid root-cause repair before any new DeepSeek run. It treats token burn as an agent-framework quality symptom, not as a narrow budget issue.

Root causes:

- AIE previously reported specialist `input_rows_by_agent` from quality-audit / data-view rows when available. That overstated actual prompt rows and made product / industry specialists look like they each consumed `48` rows even when runtime route summaries bounded prompts more tightly.
- Specialist prompt-row compaction preserved nearly every non-empty field, so internal source metadata, row-level URLs, repeated boundary prose, and low-value nested fields leaked across agents after selection.
- Product specialist payload was dominated by `bounded_evidence_rows` plus `product_spec_pack`, with product sections sending too many rows and large summary / boundary metadata.
- Memo Writer / Verifier compact views still carried long role instructions and broad required-item / product reasoning scaffolds after the earlier duplicate-view coalescing.

Repair:

- `src/sec_agent/agent_information_economy.py` now prefers route-summary `prompt_bounded_evidence_row_count` for `input_rows_by_agent`, preserves previous data-view row counts separately as `data_view_rows_by_agent`, and records `input_row_measurement_boundary=prompt_bounded_evidence_row_count_from_route_summary`.
- `src/sec_agent/specialist_llm.py` now projects prompt rows through source-family-specific allowlists rather than forwarding all non-empty fields. Product fields stay with product graph rows, public binding fields stay with public/live web rows, relationship fields stay with relationship graph rows, and numeric fields stay with SEC / market / industry / product sources.
- `ProductSpecPack` prompt sections default from `6` to `3` items, and summary / boundary metadata is compacted recursively before it reaches the specialist prompt.
- `src/sec_agent/memo_llm.py` further shortens compact writer/verifier payload fields, required-item prompts, product reasoning frames, economic-role summaries, ClaimCard text, and verifier direct-answer / supported-claim projections.
- Regression coverage now includes AIE measurement-boundary preference and specialist row projection preserving public web entity binding metadata without reopening broad row leakage.

No-paid diagnostic evidence:

- Compared no-paid semicap mock runs `p30_mock_semicap_aie_prompt_row_metric2_20260703` and `p30_mock_semicap_source_family_row_projection_20260703`.
- Specialist prompt payload total fell from `67,047` to `33,489` approximate chars.
- Product specialist payload fell from `41,607` to `15,577` chars:
  - bounded rows `22,586 -> 12,005`
  - product spec pack `19,021 -> 3,572`
- Industry / supply-chain specialist payload fell from `22,255` to `15,899` chars:
  - bounded rows `15,289 -> 10,749`
  - relationship summary `6,522 -> 4,706`
- AIE now reports actual prompt rows as:
  - `fundamental_analyst=5`
  - `product_technology_analyst=24`
  - `industry_supply_chain_analyst=20`
  - `risk_counterevidence_analyst=10`
- AIE still exposes data-view rows separately:
  - `product_technology_analyst=48`
  - `industry_supply_chain_analyst=48`
- Memo Writer payload remains `64,654` chars and Verifier payload remains `23,391` chars after the latest specialist-specific compaction; the next no-paid target is still memo-side planning compression, especially `memo_logic_plan` and `verified_judgment_plan`.

Focused verification:

```powershell
python -m pytest tests/test_agent_information_economy.py::test_agent_information_economy_prefers_prompt_row_counts_over_data_view_counts tests/test_multi_agent_specialist_llm.py::test_build_specialist_request_from_state_uses_deep_research_prompt_budget tests/test_multi_agent_specialist_llm.py::test_prompt_pack_compaction_caps_large_product_and_fundamental_rows tests/test_multi_agent_specialist_llm.py::test_specialist_prompt_uses_source_family_summary_budgets tests/test_multi_agent_specialist_llm.py::test_specialist_request_preserves_public_web_entity_binding_metadata tests/test_multi_agent_evidence_requirements.py::test_industry_supply_chain_data_view_uses_bounded_industry_and_relationship_rows tests/test_multi_agent_evidence_requirements.py::test_product_data_view_exposes_bounded_gap_when_product_sources_requested_but_empty tests/test_ai_semis_product_evidence_pack.py::test_research_lead_and_product_agent_receive_depth_pack_ref -q
```

Result: `8 passed`.

Boundary:

- No paid LLM call was made.
- The mock full-chain summaries still have `gate_status=fail` and `diagnostic_only=true` by design because this path intentionally skips real Research Lead, retrieval, specialists, Memo Writer, and Verifier calls.
- This closes a real information-transfer and measurement-boundary defect, but not paid memo-quality acceptance.

## 2026-07-03 Memo-Side Planning Projection Compression

This update continues the same root-cause rule: reduce token burn by fixing invalid or low-value inter-agent transfer before any new paid DeepSeek run. It does not add a budget-only fallback.

Root causes found in the memo-side payload:

- `answer_first_outline` was copied too broadly into the writer payload, even though the writer only needs the thesis, dimension ids, decision-changing refs, and a short opening instruction.
- `MemoLogicPlan.sections`, `evidence_to_thesis_bridge`, `required_item_answer_plan`, and `product_reasoning_frame` repeated long instructions, repeated refs, and long required-item / product reasoning scaffolds after the ClaimCard and judgment selection steps had already happened.
- `verified_judgment_plan` still carried verbose `supported_claims`, `judgment_state`, `memo_thesis_plan`, and `memo_outline` views. These are useful for audit, but the writer/verifier route needs compact decision inputs, not another near-full plan.
- Compact ClaimCards still carried empty optional fields, long parser diagnosis rows, and verbose analyst-depth / parser-status text after selection.
- Verifier compact view still kept more direct-answer / dimension-analysis / claim text than needed for checking refs, boundaries, and missing claims.

Repair:

- `src/sec_agent/memo_llm.py` now projects `answer_first_outline` through a dedicated compact helper.
- `MemoLogicPlan` compact projection now trims section instructions, bridge rows, required-item prompts, product reasoning frames, and per-role evidence-ref lists.
- Writer-facing `writer_thesis_skeleton`, `required_item_answer_plan`, `product_reasoning_frame`, `ClaimCard`, parser diagnosis, analyst-depth, and memo-thesis plan projections now use tighter field caps and drop empty optional fields.
- Verifier-facing memo projection now trims direct answer, dimension analyses, loose section lists, and memo claims while preserving evidence refs and claim ids.

No-paid projection evidence from the latest saved semicap artifact:

- `memo_logic_plan` compact component: `27,618 -> 23,423` approximate chars.
- `verified_judgment_plan` deep compact component: `24,346 -> 20,093` approximate chars.
- Projected Memo Writer payload reduction from those two components alone: about `64,654 -> 56,206` approximate chars, before any further `supervising_analyst_pack` or fixed-instruction prompt overhead work.
- The largest remaining writer-side components are still `memo_logic_plan`, `verified_judgment_plan`, `supervising_analyst_pack`, and `shared_memo_context`; this means the next root-cause target is not another broad gate, but deciding which of those components should be route-specific writer input versus audit-only artifact.

No-paid runtime probe:

- Run artifact: `reports/r53_r60_p30_full_chain_ai_semis/p30_mock_semicap_memo_side_compaction_20260703/p30_mock_semicap_memo_side_compaction_20260703/`.
- AIE case ledger still passes for the mock probe and reports actual specialist prompt rows from route summaries:
  - `fundamental_analyst=5`
  - `product_technology_analyst=24`
  - `industry_supply_chain_analyst=20`
  - `risk_counterevidence_analyst=10`
- The mock route did not persist detailed Memo Writer / Verifier input fingerprints in `llm_routes` for this specific run, so the memo-side payload proof above is from deterministic helper projection over the saved artifact rather than runtime route storage. That is an observability boundary to keep open; it is not a paid-quality closeout.
- Overall runner gate remains `fail` by design because `llm_backend=mock` skips real Research Lead, retrieval, specialists, Memo Writer, Verifier, and run-audit tables required by this case.

Focused verification:

```powershell
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_memo_logic_plan_compaction_does_not_duplicate_required_item_prompts tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_route_records_input_pack_fingerprint_without_prompt_text tests/test_multi_agent_memo_llm_repair.py::test_verifier_projection_does_not_duplicate_memo_supported_claims_when_memo_claims_exist tests/test_multi_agent_memo_llm_repair.py::test_verifier_route_records_input_pack_fingerprint_without_prompt_text tests/test_agent_information_economy.py::test_agent_information_economy_reads_memo_writer_input_fingerprint tests/test_agent_information_economy.py::test_agent_information_economy_reads_verifier_input_fingerprint tests/test_agent_information_economy.py::test_agent_information_economy_prefers_prompt_row_counts_over_data_view_counts tests/test_multi_agent_specialist_llm.py::test_build_specialist_request_from_state_uses_deep_research_prompt_budget tests/test_multi_agent_specialist_llm.py::test_prompt_pack_compaction_caps_large_product_and_fundamental_rows tests/test_multi_agent_specialist_llm.py::test_specialist_prompt_uses_source_family_summary_budgets tests/test_multi_agent_specialist_llm.py::test_specialist_request_preserves_public_web_entity_binding_metadata -q
python -m compileall -q src/sec_agent/memo_llm.py src/sec_agent/specialist_llm.py src/sec_agent/agent_information_economy.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py tests/test_agent_information_economy.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_memo_llm_repair.py
git diff --check -- src/sec_agent/memo_llm.py src/sec_agent/specialist_llm.py src/sec_agent/agent_information_economy.py tests/test_agent_information_economy.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_memo_llm_repair.py docs/worklog/product_strategy/068_p30_agent_information_economy_runtime_ledger.md docs/worklog/README.md docs/worklog/00_internal_master_checklist.md
```

Result: `11 passed`; compileall pass; diff check pass; narrowed secret scan found no plaintext secrets.

Boundary:

- No paid LLM call was made.
- This is a root-cause compression repair for memo-side information transfer, not a claim that memo quality is now accepted.
- Before any paid rerun, the next deterministic target should either persist mock-route Memo Writer / Verifier fingerprints consistently or further split writer input into route-specific decision payload versus audit-only planning artifacts.

## 2026-07-03 Mock Route Memo / Verifier Fingerprint Persistence

This update closes the observability boundary found by the previous no-paid run. The root cause was not external data or model quality: when `llm_backend=mock`, the graph does not inject `memo_writer_from_env` / `verifier_from_env`, so it uses orchestrator stub branches. Those stub branches produced memo / verifier artifacts but did not persist the same input-pack fingerprints that real LLM routes persist.

Repair:

- `src/sec_agent/memo_llm.py` now exposes deterministic wrappers:
  - `memo_writer_input_pack_fingerprint_for_state(...)`
  - `verifier_input_projection_for_state(...)`
- `src/sec_agent/langgraph_orchestrator.py` now attaches digest-only `memo_route_result.input_pack_fingerprint` in the stub Memo Writer branch.
- The Verifier node now attaches `claim_verification.verifier_input_projection.input_pack_fingerprint` and `claim_verification.verifier_input_pack_fingerprint` even when the verifier is deterministic / stubbed or injected without its own projection.
- The persisted fingerprints keep `capture_source`, component digests, approximate component chars, evidence-ref counts, and no prompt text.

No-paid runtime proof:

- Run artifact: `reports/r53_r60_p30_full_chain_ai_semis/p30_mock_semicap_stub_fingerprint_persistence_20260703/p30_mock_semicap_stub_fingerprint_persistence_20260703/`.
- `multi_agent_summary.llm_routes.memo_writer.route_result.input_pack_fingerprint` is now present:
  - `capture_source=deterministic_stub_using_memo_writer_input_contract`
  - `approx_prompt_payload_chars=56,206`
  - component chars: `shared_memo_context=4,722`, `supervising_analyst_pack=7,800`, `memo_logic_plan=23,423`, `verified_judgment_plan=20,093`, `specialist_verification=168`
- `multi_agent_summary.llm_routes.verifier.input_projection.input_pack_fingerprint` is now present:
  - `capture_source=deterministic_stub_using_verifier_projection_contract`
  - `approx_prompt_payload_chars=19,504`
  - component chars: `memo_answer=10,857`, `memo_claim_ref_inventory=5,943`, `allowed_evidence_refs=2,350`, `source_boundary_notes=2`, `deterministic_verification=352`
- AIE result for this mock probe remains `status=pass`, `issue_counts={}`, with specialist prompt rows still measured from route summaries:
  - `fundamental_analyst=5`
  - `product_technology_analyst=24`
  - `industry_supply_chain_analyst=20`
  - `risk_counterevidence_analyst=10`
- Overall runner gate remains `fail` by design because `llm_backend=mock` skips real Research Lead, retrieval, specialists, Memo Writer, Verifier, and required run-audit tables. This run is an observability/contract proof only.

Focused verification:

```powershell
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_stub_memo_and_verifier_routes_persist_input_fingerprints tests/test_multi_agent_memo_llm_repair.py::test_memo_logic_plan_compaction_does_not_duplicate_required_item_prompts tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_route_records_input_pack_fingerprint_without_prompt_text tests/test_multi_agent_memo_llm_repair.py::test_verifier_projection_does_not_duplicate_memo_supported_claims_when_memo_claims_exist tests/test_multi_agent_memo_llm_repair.py::test_verifier_route_records_input_pack_fingerprint_without_prompt_text tests/test_multi_agent_real_llm_chain_eval.py::test_agent_audit_projects_input_fingerprints_for_deterministic_routes tests/test_agent_information_economy.py::test_agent_information_economy_reads_memo_writer_input_fingerprint tests/test_agent_information_economy.py::test_agent_information_economy_reads_verifier_input_fingerprint tests/test_agent_information_economy.py::test_agent_information_economy_prefers_prompt_row_counts_over_data_view_counts tests/test_multi_agent_specialist_llm.py::test_specialist_prompt_uses_source_family_summary_budgets -q
python -m compileall -q src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_agent_information_economy.py tests/test_multi_agent_specialist_llm.py
git diff --check -- src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_agent_information_economy.py tests/test_multi_agent_specialist_llm.py docs/worklog/product_strategy/068_p30_agent_information_economy_runtime_ledger.md docs/worklog/README.md docs/worklog/00_internal_master_checklist.md
```

Result: `10 passed`; compileall pass; diff check pass; narrowed secret scan found no plaintext secrets.

## 2026-07-03 Supervising / Shared Memo Context Projection Compression

This update continues the product-core Agent Information Economy repair. The goal is not to blindly save tokens; it is to remove invalid or low-value agent-to-agent transfer before spending paid LLM calls.

Root causes found:

- `shared_memo_context` still passed the LeadReview object too broadly into the Memo Writer payload. Writer needed stance, objective coverage, gap policy, product-output contract, targeted-repair summary, and supervising core stance; it did not need raw lead/debug/result objects.
- `prompt_policy.allowed_input_views` and similar audit-only policy fields were repeatedly copied into writer input even though they are stable runtime contracts.
- `supervising_analyst_pack.product_bridge_pack.coverage` carried nested depth/layer status maps that are useful for audit but not for writer reasoning.
- Product bridge rows included empty optional fields such as blank `display_value`, blank `claim_id`, and over-wide ticker/product lists.
- `supervision_findings.required_followups` could repeat identical owner/action rows.

Repair:

- `src/sec_agent/memo_llm.py` now compacts LeadReview through `_compact_shared_lead_review_for_prompt(...)`, keeping only writer-facing stance / objective / gap / product-output / targeted-repair / supervising summary fields.
- `prompt_policy` projection now keeps only short policy labels and exclusion rules; `allowed_input_views` no longer enters the prompt projection.
- `product_bridge_pack.coverage` now uses `_compact_product_bridge_coverage_for_writer(...)`, keeping booleans, exact/proxy counts, gap count, and layer names rather than nested gate objects.
- Product-KPI and official product context rows drop empty optional fields and cap writer-facing row counts to the top four.
- Supervision findings and follow-ups are capped and deduped by owner/action.

No-paid runtime proof:

- Run artifact: `reports/r53_r60_p30_full_chain_ai_semis/p30_mock_semicap_supervising_shared_compaction_20260703/p30_mock_semicap_supervising_shared_compaction_20260703/`.
- Compared with `p30_mock_semicap_stub_fingerprint_persistence_20260703`:
  - Memo Writer projected payload: `56,206 -> 53,307` approximate chars.
  - `shared_memo_context`: `4,722 -> 3,947` approximate chars.
  - `supervising_analyst_pack`: `7,800 -> 5,676` approximate chars.
  - Verifier projected payload remained `19,504` approximate chars, as expected, because this repair only touched writer-side shared/supervising projections.
- Overall runner gate remains `fail` by design under `llm_backend=mock`; this is a deterministic information-transfer proof, not a paid memo-quality closeout.

Focused verification:

```powershell
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_stub_memo_and_verifier_routes_persist_input_fingerprints tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_prompt_projection_compacts_supervising_and_shared_context tests/test_multi_agent_memo_llm_repair.py::test_memo_logic_plan_compaction_does_not_duplicate_required_item_prompts tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_route_records_input_pack_fingerprint_without_prompt_text tests/test_multi_agent_memo_llm_repair.py::test_verifier_projection_does_not_duplicate_memo_supported_claims_when_memo_claims_exist tests/test_multi_agent_memo_llm_repair.py::test_verifier_route_records_input_pack_fingerprint_without_prompt_text tests/test_multi_agent_real_llm_chain_eval.py::test_agent_audit_projects_input_fingerprints_for_deterministic_routes tests/test_agent_information_economy.py::test_agent_information_economy_reads_memo_writer_input_fingerprint tests/test_agent_information_economy.py::test_agent_information_economy_reads_verifier_input_fingerprint tests/test_agent_information_economy.py::test_agent_information_economy_prefers_prompt_row_counts_over_data_view_counts tests/test_multi_agent_specialist_llm.py::test_specialist_prompt_uses_source_family_summary_budgets -q
python -m compileall -q src/sec_agent/memo_llm.py tests/test_multi_agent_memo_llm_repair.py
```

Result: `11 passed`; compileall pass.

Boundary:

- No paid LLM call was made.
- This closes the obvious shared/supervising projection bloat, but not the overall memo-quality problem. The largest remaining writer-side components are still `memo_logic_plan=23,423` and `verified_judgment_plan=20,093` approximate chars in the mock artifact.

## 2026-07-03 MemoLogicPlan / VerifiedJudgment Writer Projection Compression

This update targets the next writer-side root cause after shared/supervising context: the same required item and thesis structure appeared in multiple writer inputs.

Root causes found:

- Required-item direction was repeated across `required_question_items`, `required_item_answer_plan`, section-level instructions, `writer_thesis_skeleton.dimension_moves`, and `evidence_to_thesis_bridge`.
- Product reasoning references carried up to three refs per layer even though the writer only needs a small decision spine; full refs remain in artifacts and audit ledgers.
- Section writing instructions and evidence-to-thesis bridge instructions were longer than needed after `required_item_answer_plan` became the primary required-item writing contract.
- `verified_judgment_plan` carried several overlapping summary views: `judgment_state`, `memo_thesis_plan`, `memo_thesis_pack`, `memo_outline`, and `thesis_driver_pack`. These are not deleted, but writer projection should be shorter.

Repair:

- `memo_logic_plan` compact projection now reduces section ref caps, required-item terms, evidence bridge refs, section writing instructions, thesis skeleton move text, product reasoning refs, and required-item answer prompts.
- `verified_judgment_plan` compact projection now trims `memo_thesis_plan` and `judgment_state` prose/refs while preserving claim ids, evidence refs, stance, and dimension skeleton.
- The full planning artifacts remain available as saved case artifacts; this change only narrows route input.

No-paid runtime proof:

- Run artifact: `reports/r53_r60_p30_full_chain_ai_semis/p30_mock_semicap_memo_plan_judgment_projection_compaction_20260703/p30_mock_semicap_memo_plan_judgment_projection_compaction_20260703/`.
- Compared with `p30_mock_semicap_stub_fingerprint_persistence_20260703`:
  - Memo Writer projected payload: `56,206 -> 49,350` approximate chars.
  - `shared_memo_context`: `4,722 -> 3,947`.
  - `supervising_analyst_pack`: `7,800 -> 5,676`.
  - `memo_logic_plan`: `23,423 -> 20,736`.
  - `verified_judgment_plan`: `20,093 -> 18,823`.
  - Verifier projected payload remains `19,504` approximate chars.
- Compared only with the prior shared/supervising repair, this step reduces Memo Writer payload `53,307 -> 49,350`.
- Overall runner gate remains `fail` by design under `llm_backend=mock`; no paid model call was made.

Focused verification:

```powershell
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_stub_memo_and_verifier_routes_persist_input_fingerprints tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_prompt_projection_compacts_supervising_and_shared_context tests/test_multi_agent_memo_llm_repair.py::test_memo_logic_plan_compaction_does_not_duplicate_required_item_prompts tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_route_records_input_pack_fingerprint_without_prompt_text tests/test_multi_agent_memo_llm_repair.py::test_verifier_projection_does_not_duplicate_memo_supported_claims_when_memo_claims_exist tests/test_multi_agent_memo_llm_repair.py::test_verifier_route_records_input_pack_fingerprint_without_prompt_text tests/test_multi_agent_real_llm_chain_eval.py::test_agent_audit_projects_input_fingerprints_for_deterministic_routes tests/test_agent_information_economy.py::test_agent_information_economy_reads_memo_writer_input_fingerprint tests/test_agent_information_economy.py::test_agent_information_economy_reads_verifier_input_fingerprint tests/test_agent_information_economy.py::test_agent_information_economy_prefers_prompt_row_counts_over_data_view_counts tests/test_multi_agent_specialist_llm.py::test_specialist_prompt_uses_source_family_summary_budgets -q
python -m compileall -q src/sec_agent/memo_llm.py tests/test_multi_agent_memo_llm_repair.py
```

Result: `11 passed`; compileall pass.

Boundary:

- This is still deterministic projection repair. It does not prove the final memo is good.
- The next no-paid target should be the fixed Memo Writer prompt scaffolding / output contract and verifier projection, not another broad full-chain paid rerun.

## 2026-07-03 Memo Writer Static Scaffold Compression / Fingerprint

This update fixes a measurement and transfer gap outside the input JSON pack. The previous fingerprint measured compact payload components but not the fixed Memo Writer prompt instructions, so AIE could still underestimate real prompt cost.

Root causes found:

- The Memo Writer user prompt carried about `8,138` characters before `Input JSON:` in the semicap probe.
- That fixed instruction block repeated rules already represented in `memo_input_contract`, `memo_output_contract`, `memo_logic_plan`, and the skill system prompt.
- The input-pack fingerprint did not include any digest or length record for fixed scaffold text, so changing prompt policy would not change the main fingerprint digest.

Repair:

- Added `_memo_writer_compact_instruction_scaffold(...)` and route-level override so the sent Memo Writer user instruction is compact while preserving the required contract terms: `ClaimCard`, `shared_memo_context`, `memo_outline`, `memo_thesis_plan`, `memo_thesis_pack`, `thesis_driver_pack`, `writer_thesis_skeleton`, `thesis_density_contract`, `do_not_emit_supported_claims`, and `memo_writer_v0_9_writer_thesis_skeleton_first_readable_surface`.
- Added `static_prompt_scaffold_summary` to `memo_route_result.input_pack_fingerprint`.
- Added `approx_total_prompt_chars_with_scaffold` so AIE can distinguish JSON payload size from total route prompt estimate.
- The scaffold summary stores only policy id, character counts, and digests. It does not persist prompt text.

No-paid runtime proof:

- Run artifact: `reports/r53_r60_p30_full_chain_ai_semis/p30_mock_semicap_static_scaffold_fingerprint_digest_20260703/p30_mock_semicap_static_scaffold_fingerprint_digest_20260703/`.
- Memo Writer fingerprint:
  - `digest=sha256:e0e2723385ba8e96`
  - `approx_prompt_payload_chars=49,350`
  - `approx_total_prompt_chars_with_scaffold=54,308`
  - `static_prompt_scaffold_summary.policy_id=memo_writer_compact_instruction_scaffold_v0_1`
  - `system_prompt_chars=2,076`
  - `user_instruction_chars=2,882`
  - `system_prompt_digest=sha256:422101c254867c5e`
  - `user_instruction_digest=sha256:4858999c135c2910`
- Direct message measurement on the same case shows Memo Writer user prompt before `Input JSON:` is now `2,873` characters, down from the prior `8,138` measurement.
- Overall runner gate remains `fail` by design under `llm_backend=mock`; no paid model call was made.

Focused verification:

```powershell
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_llm_accepts_valid_memo_json tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_route_records_input_pack_fingerprint_without_prompt_text tests/test_multi_agent_memo_llm_repair.py::test_stub_memo_and_verifier_routes_persist_input_fingerprints -q
```

Result: `3 passed`; compileall pass.

Boundary:

- This repairs Memo Writer fixed-scaffold observability and prompt transfer. It does not yet compress Verifier static system prompt or verifier projection payload.

## 2026-07-03 Verifier Projection / Static Scaffold Compression

This update fixes the next no-paid prompt-economy target after Memo Writer compression. The root cause was again owned information transfer, not external data: Verifier was receiving a repeated writing-oriented memo view plus a mini ClaimCard inventory and its fixed system scaffold was not represented in the input fingerprint.

Repair:

- Reduced Verifier skill system scaffold from `research_skill_prompt("verifier", max_chars=3000)` to `max_chars=1600` while preserving the JSON-only, no-tools, bounded-block, and evidence-ref-boundary rules.
- Added `_verifier_user_instruction_scaffold(...)` and `static_prompt_scaffold_summary` to `verifier_input_pack_fingerprint`.
- Added `approx_total_prompt_chars_with_scaffold` so AIE can compare payload-only and total route prompt estimates.
- Compressed `memo_answer` for verifier by shortening direct answer, dimension analyses, loose sections, and non-critical views.
- Changed `memo_claim_ref_inventory` from a repeated mini ClaimCard view to `memo_intersection_refs_only_v0_1`, keeping claim id / agent / short claim / source families / memo-intersecting evidence refs.

No-paid runtime proof:

- Run artifact: `reports/r53_r60_p30_full_chain_ai_semis/p30_mock_semicap_verifier_projection_scaffold_compaction_20260703/`.
- Compared with the prior mock summary:
  - Verifier projected payload `19504 -> 15149` chars.
  - Verifier total prompt estimate now recorded as `17414` chars.
  - Verifier system scaffold `3256 -> 2074` chars.
  - `known_evidence_ref_count` is `21`, reduced from the prior `39` because the inventory now follows final memo-intersecting refs instead of forwarding unrelated projected refs.
  - Memo Writer remains in the expected range: payload `49362`, total prompt estimate `54320`.
- Overall runner gate remains `fail` by design under `llm_backend=mock`; no paid model call was made.

Focused verification:

```powershell
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_verifier_projection_does_not_duplicate_memo_supported_claims_when_memo_claims_exist tests/test_multi_agent_memo_llm_repair.py::test_verifier_route_records_input_pack_fingerprint_without_prompt_text tests/test_multi_agent_memo_llm_repair.py::test_verifier_llm_uses_minimal_memo_claim_projection tests/test_agent_information_economy.py::test_agent_information_economy_reads_verifier_input_fingerprint -q
```

Result: `4 passed`; compileall pass.

Boundary:

- This closes Verifier-side prompt/projection waste visible in the no-paid artifact. It does not prove real DeepSeek memo quality, and it does not authorize broad 20-50 full-chain runs.

No-paid budget preflight after this repair:

- Single semicap case `p30_preflight_semicap_after_verifier_compaction_20260703`: `status=allowed`, `estimated_total_tokens=101400`, `estimated_paid_call_count=8`.
- Two AI/Semis case batch `p30_preflight_two_ai_semis_after_verifier_compaction_20260703`: `status=blocked_preflight_token_budget`, `estimated_total_tokens=202800`, `estimated_paid_call_count=16`; scheduler advice remains `split_required`, with one paid case per batch.
- Interpretation: the gate now prevents accidental two-case paid launches. A real DeepSeek run, if approved, should be a single case only after the latest deterministic checks pass.

## 2026-07-03 Evidence-Operator Mode Guard / Paid-Run Containment

User-approved single-case paid run `p30_paid_semicap_after_information_economy_compaction_20260703_r1` exposed an owned runner-contract bug rather than a valid memo-quality result.

Observed failure:

- The command did not pass `--real-evidence-operators`.
- The case contract requires real retrieval/evidence quality, but the runner allowed paid LLM execution with dry-run evidence operators.
- The run failed with `evidence_operators.sec_search_not_dry_run=false`, missing BM25/BGE/runtime-ledger evidence checks, weak specialist evidence quality, and low memo/verifier surface quality.
- This artifact is therefore invalid as product-quality acceptance evidence. It is useful only as a root-cause signal: never spend paid model calls on a case whose evidence operators are still in dry-run mode.

Repair:

- `eval_multi_agent_real_llm_chain.py` now adds `evidence_operator_mode_policy=paid_real_retrieval_cases_require_real_evidence_operators_v0_1`.
- Paid runs whose case catalog rows require real retrieval/evidence quality now fail closed before graph/model execution unless `--real-evidence-operators` is present.
- The evidence-mode blocker is separate from token-budget blockers: scheduler advice can still report that one paid case is within budget while the run is blocked because evidence mode is wrong.
- `--allow-expensive-llm` does not override evidence-mode violations.

No-paid verification:

- Guard probe without `--real-evidence-operators`: `p30_preflight_semicap_evidence_mode_guard_20260703_r2` exits before graph/model with `status=blocked_preflight_evidence_operator_mode`, no token-budget violation, and required action to pass `--real-evidence-operators`.
- Real-evidence preflight with `--real-evidence-operators --token-budget-preflight-only`: `p30_preflight_semicap_real_evidence_allowed_20260703` is `status=allowed`, `estimated_total_tokens=101400`, `estimated_paid_call_count=8`.
- Real-evidence no-paid/mock smoke `p30_mock_semicap_real_evidence_operator_smoke_20260703` confirms retrieval is now real: `sec_search_not_dry_run=true`, BM25 candidates present, BGE rerank present, runtime ledger rows present, `context_runner=in_process`, `bge_device=cuda`, `context_row_count=99`, `runtime_ledger_row_count=29`. Overall gate remains `fail` because mock specialists fail real-LLM route quality by design.

Focused verification:

```powershell
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_blocks_expensive_paid_run tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_preflight_blocks_paid_real_retrieval_case_without_real_evidence_operators tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_preflight_allows_paid_real_retrieval_case_with_real_evidence_operators tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_token_budget_preflight_only_writes_plan_without_graph tests/test_multi_agent_real_llm_chain_eval.py::test_agent_audit_projects_input_fingerprints_for_deterministic_routes -q
```

Result: `5 passed`; compileall pass.

Boundary:

- No additional paid rerun was launched after the invalid r1 run.
- The next paid run, if explicitly approved, must be a single case with `--real-evidence-operators`, after deterministic real-evidence smoke and token preflight both pass.

## 2026-07-03 Valid Paid Single-Case Result / Renderer Root-Cause Repair

After the evidence-operator guard and real-evidence mock smoke passed, one user-approved paid single-case run was launched with real evidence operators:

```powershell
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py `
  --case-catalog-path tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json `
  --case-id fin_deep_semicap_asml_amat_lrcx_klac_cycle_025 `
  --real-evidence-operators `
  --output-dir reports/r53_r60_p30_full_chain_ai_semis `
  --run-id p30_paid_semicap_real_evidence_after_information_economy_guard_20260703_r1 `
  --token-budget-total 180000 `
  --token-budget-per-case 120000 `
  --max-paid-calls 8
```

Result:

- Run artifact: `reports/r53_r60_p30_full_chain_ai_semis/p30_paid_semicap_real_evidence_after_information_economy_guard_20260703_r1/`.
- Runner completed, but product gate remained `fail`; this is a diagnostic artifact, not product acceptance.
- Retrieval / evidence operators passed: SEC search was not dry-run, BM25 candidates were present, BGE rerank ran, runtime-ledger rows existed, and market / industry / relationship rows were present.
- Specialist and supervising layers passed their route-quality checks.
- Failure moved downstream to memo surface / final-answer quality and AIE cost-quality:
  - `memo_verifier.surface.no_internal_field_labels=false`
  - `memo_verifier.quality.internal_gate_prose_absent=false`
  - `memo_verifier.quality.dimension_number_sequence_ok=false`
  - `output_cost_quality_blocked=true`
  - high prompt transfer remained: Memo Writer fingerprint showed roughly `memo_logic_plan=34.9k`, `verified_judgment_plan=24.4k`, `supervising_analyst_pack=15.9k`.

Root-cause diagnosis:

- `dimension_number_sequence_ok=false` was an evaluator extraction bug: the dimension section parser did not stop before `关键问题回应`, so the next section's numbered list looked like dimension numbering restarted.
- `internal_gate_prose_absent=false` was caused by owned renderer/salvage wording leaking instruction-like phrases such as `投资判断应先...`.
- `no_internal_field_labels=false` was caused by required-item projection wording (`证据锚点`) and a second ClaimCard-like numbered ledger being rendered after the actual dimension analysis.
- These were internal renderer / projection / eval defects, not missing public data and not a model-provider issue.

Repair:

- `langgraph_orchestrator._render_memo_answer(...)` now suppresses the duplicate ClaimCard-like `关键论据` ledger when a standard / expanded / deep-research memo already has a dense `分维度分析` surface.
- Required-item projection now uses user-facing language such as `当前可确认的是...` instead of internal audit terms such as `证据锚点` or `artifact`.
- Salvage / render cleanup removes the old instruction-like `投资判断应先...` phrasing and rewrites it as a judgment frame.
- `eval_multi_agent_real_llm_chain._extract_dimension_section(...)` now stops before `关键问题回应` / `Required question coverage`.

No-paid replay proof:

- Re-rendered the paid artifact's saved `memo_answer.json` locally through the repaired renderer. No LLM call was made.
- Replay result:
  - `surface_status=pass`
  - `surface_failed=[]`
  - `quality_status=pass`
  - `quality_failed=[]`
  - `dimension_number_sequence_ok=true`
  - `gap_sentence_ratio=0.0417`
  - `insight_sentence_count=20`
- Interpretation: the paid artifact's downstream renderer / eval defects are repaired deterministically. This does not prove a new full-chain pass because the paid run itself was not re-executed under the new code.

Focused verification:

```powershell
python -m compileall -q src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_required_item_projection_uses_user_facing_evidence_phrase tests/test_multi_agent_memo_llm_repair.py::test_deep_memo_renderer_uses_dimension_surface_instead_of_claim_ledger tests/test_multi_agent_memo_llm_repair.py::test_salvage_direct_answer_tail_is_judgment_frame_not_internal_instruction tests/test_multi_agent_memo_llm_repair.py::test_memo_renderer_hides_inline_internal_refs_and_metric_ids tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_salvages_repeated_length_failures_as_verifiable_memo tests/test_multi_agent_real_llm_chain_eval.py::test_dimension_number_sequence_stops_before_required_question_section tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_preflight_blocks_paid_real_retrieval_case_without_real_evidence_operators tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_preflight_allows_paid_real_retrieval_case_with_real_evidence_operators -q
```

Result: `8 passed`.

Boundary:

- No second paid run was launched after this deterministic repair.
- The remaining blocker before another paid full-chain attempt is information-economy compression on the real-run writer payload: `memo_logic_plan`, `verified_judgment_plan`, and `supervising_analyst_pack` are still too large relative to the rendered memo yield.
- Next repair should use no-paid fingerprint / replay analysis first; only after prompt-transfer density improves should a new single-case paid run be considered.

## 2026-07-03 Writer Payload Budget / Duplicate-Transfer Repair

The next no-paid audit used the same saved semicap paid artifact to inspect Memo Writer input size. This confirmed the defect was not merely "high token budget" but an owned information-transfer problem:

- `memo_logic_plan`, `verified_judgment_plan`, and `supervising_analyst_pack` repeated long `evidence_refs` and fallback planning views.
- Some supervising financial rows had no `display_value` but were still sent to the writer, adding noise without usable memo content.
- Writer received multiple overlapping plan layers (`required_question_items`, `required_item_answer_plan`, `sections`, `judgment_state`, `thesis_driver_pack`) instead of a harder Research-Lead-first projection.

Repair:

- Added `MemoWriterBudgetSpec` and profile-aware writer budgets for `compact / standard / expanded / deep_research`.
- Routed the same budget into both actual `_memo_messages(...)` and `memo_writer_input_pack_fingerprint_for_state(...)`, so audit metrics now match the real prompt projection.
- Removed duplicated long `evidence_refs` from non-claim plan/supervising packs; the writer should cite through selected verified claims, not through every intermediate plan row.
- Filtered supervising financial/product rows without `display_value` before they enter writer payload.
- Removed writer-unneeded `analyst_depth` / parser-diagnosis debug fields from compact ClaimCards; those remain upstream diagnostics, not writer input.
- Tightened deep/expanded profile budgets so "deep research" means better Lead compression, not wider prompt dumping.

No-paid replay proof on the saved semicap artifact:

- Before this repair, budget-aware replay still produced roughly:
  - `approx_total_prompt_chars_with_scaffold=75,137`
  - `memo_logic_plan=28.8k`
  - `verified_judgment_plan=24.4k`
  - `supervising_analyst_pack=13.3k`
- After duplicate-transfer repair:
  - `approx_total_prompt_chars_with_scaffold=47,019`
  - actual `_memo_messages(...)` total chars: `47,857`
  - `memo_logic_plan=16.4k`
  - `verified_judgment_plan=15.3k`
  - `supervising_analyst_pack=6.7k`
  - non-claim plan/supervising evidence-ref repeats: `0`
  - known writer evidence refs: `7`
- This is a deterministic replay only. It reduces the next paid writer prompt surface, but does not claim a new full-chain product pass.

Focused verification:

```powershell
python -m compileall -q src/sec_agent/memo_llm.py tests/test_multi_agent_memo_llm_repair.py
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_prompt_projection_compacts_supervising_and_shared_context tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_budget_projection_removes_plan_refs_and_claim_debug_fields tests/test_multi_agent_memo_llm_repair.py::test_required_item_projection_uses_user_facing_evidence_phrase tests/test_multi_agent_memo_llm_repair.py::test_deep_memo_renderer_uses_dimension_surface_instead_of_claim_ledger tests/test_multi_agent_memo_llm_repair.py::test_salvage_direct_answer_tail_is_judgment_frame_not_internal_instruction tests/test_multi_agent_real_llm_chain_eval.py::test_dimension_number_sequence_stops_before_required_question_section tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_preflight_blocks_paid_real_retrieval_case_without_real_evidence_operators tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_preflight_allows_paid_real_retrieval_case_with_real_evidence_operators -q
```

Result: `8 passed`.

Boundary:

- This fixes an owned information-transfer defect and adds regression protection.
- It does not yet prove specialist fanout is always sufficiently narrow, nor does it prove a fresh DeepSeek full-chain pass.
- The next paid run remains blocked until the no-paid artifact replay / preflight shows acceptable route selection, prompt size, and case budget for one case.

## 2026-07-03 Specialist Fanout Decision Ledger / Catalog Context Repair

This update closes the next no-paid pre-rerun blocker: specialist fanout and routing had to be explainable before any additional paid full-chain case.

Root causes found:

- Saved paid diagnostic artifact `p30_paid_semicap_real_evidence_after_information_economy_guard_20260703_r1` ran five specialists, but did not persist `specialist_activation_decisions`, so the runtime could not explain why market / risk were active.
- `AgentInformationEconomyLedger` counted every route result as active, including skipped routes, which made token-spending fanout analysis less precise.
- Required-item / explicit-intent matching under-recognized Chinese AI/Semis and semicap terms such as `订单`, `积压`, `出货`, `客户集中`, `出口限制`, `出口管制`, `估值`, `资金面`, and `流动性`.
- `MultiAgentRouteRequest.from_dict(...)` discarded top-level catalog fields such as `source_tiers`, `metric_families`, `required_dimension_ids`, `eval_focus`, `expected_paid_specialist_agents`, `expected_paid_specialist_priorities`, and `expected_execution_mode`. This meant deterministic routing could disagree with the case catalog even when the catalog carried the correct contract.

Repair:

- `specialist_llm.py` and `langgraph_orchestrator.py` now persist route-level `activation_decision`, `activation_reason`, `matched_requirement_count`, `explicit_intent`, and `signal_count` for run and skipped specialists.
- `specialist_fanout_barrier` now records `supporting_run_without_required_item_match_count` and the exact offending agents.
- `agent_information_economy.py` now counts only non-skipped routes as active paid specialists, preserves skipped-route counts separately, and uses activation decisions to flag supporting/conditional/low-priority specialists that run without required-item match or explicit intent.
- `multi_agent_runtime.py` now includes user query / prompt / query contract / metric families / source tiers / eval focus / required dimensions in intent text, and recognizes Chinese AI/Semis / semicap required-item terms for industry, risk, product, and market activation.
- `multi_agent_router.py` now promotes catalog top-level routing fields into request context before route scoring, so route decisions are not dependent on callers manually restuffing catalog fields into `context`.

No-paid evidence:

- Replay audit over the old paid semicap artifact still fails AIE, as expected, because that artifact lacks activation decision ledger and used broad fanout:
  - `active_count=5`
  - `active_agents=fundamental_analyst, product_technology_analyst, industry_supply_chain_analyst, market_valuation_analyst, risk_counterevidence_analyst`
  - `agents_without_required_item_match=market_valuation_analyst, risk_counterevidence_analyst`
  - issue set includes `overbroad_specialist_fanout`, `specialist_without_required_item_match`, `high_total_token_cost`, `low_memo_chars_per_token`, `low_rendered_claim_token_efficiency`, `memo_payload_not_dense_enough`, `memo_writer_high_token_cost`, and `prompt_pack_overlap_proxy`.
- No-paid semicap preflight with real evidence operators remains allowed for one case at `101400` estimated tokens / `8` paid calls.
- No-paid semicap preflight without `--real-evidence-operators` still fail-closes before graph/model execution with `blocked_preflight_evidence_operator_mode`.
- Deterministic catalog route check now keeps `product_technology_analyst`, excludes non-required `market_valuation_analyst`, and aligns `expected_paid_specialist_agents` with actual planned paid specialists from the case catalog.

Verification:

```powershell
python -m compileall -q src/sec_agent/multi_agent_runtime.py src/sec_agent/multi_agent_router.py src/sec_agent/specialist_llm.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/agent_information_economy.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_routing_fixtures.py tests/test_agent_information_economy.py
python -m pytest tests/test_multi_agent_specialist_llm.py::test_specialist_env_router_runs_active_specialists_with_bounded_state tests/test_multi_agent_specialist_llm.py::test_specialist_env_router_skips_conditional_specialist_without_signal tests/test_multi_agent_specialist_llm.py::test_specialist_activation_matches_chinese_industry_and_risk_requirements tests/test_multi_agent_langgraph_routing.py::test_multi_agent_graph_standard_path_runs_specialists tests/test_multi_agent_routing_fixtures.py::test_ai_semis_catalog_paid_specialists_match_deterministic_activation tests/test_multi_agent_routing_fixtures.py::test_market_snapshot_source_does_not_force_market_valuation_specialist tests/test_agent_information_economy.py::test_agent_information_economy_fails_high_cost_low_yield_fanout tests/test_agent_information_economy.py::test_agent_information_economy_uses_activation_decisions_for_required_item_fanout tests/test_agent_information_economy.py::test_agent_information_economy_prefers_prompt_row_counts_over_data_view_counts tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_prompt_projection_compacts_supervising_and_shared_context tests/test_multi_agent_memo_llm_repair.py::test_memo_writer_budget_projection_removes_plan_refs_and_claim_debug_fields tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_preflight_blocks_paid_real_retrieval_case_without_real_evidence_operators tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_preflight_allows_paid_real_retrieval_case_with_real_evidence_operators -q
```

Result: `13 passed`.

Boundary:

- No paid LLM call was made in this repair.
- The old paid semicap artifact remains diagnostic-only and should not be promoted.
- The next paid attempt is still blocked until a fresh no-paid generated artifact proves specialist activation ledger, route selection, data/script audit, AIE preflight, and exact one-case budget all pass together.

## 2026-07-03 Role-Specific Prompt Overlap Root-Cause Repair

A fresh no-paid semicap mock artifact exposed that route/fanout was no longer the blocker, but role-specific prompt selection still leaked the same evidence refs into multiple specialists:

- `risk_counterevidence_analyst` still received ordinary financial rows shared with `fundamental_analyst`.
- `product_technology_analyst` and `industry_supply_chain_analyst` both received generic product-profile / customer-deployment refs.
- `ProductSpecPack` prompt projection still carried customer-deployment and supply-chain sections into the product specialist, creating another cross-role duplicate path.

Repair:

- `specialist_llm.py` now applies role-level row filtering before prompt ranking and fingerprinting:
  - product specialist receives product/profile/spec/KPI/channel/field-inquiry rows, not customer deployment or supply-chain edges;
  - industry specialist receives industry/relationship/deployment/order/customer/channel/supply-chain rows, not generic product profile rows;
  - risk specialist receives only real risk / constraint / counterevidence rows and no longer admits ordinary revenue/gross-margin rows through broad counterclaim-slot matching.
- Risk term matching now avoids false positives such as `process-control` being treated as export-control risk.
- Product prompt `ProductSpecPack` is role-projected to specs/KPI/channel/field-inquiry/commercial-gap sections; raw pack and repair payload still preserve customer-deployment / supply-chain sections for audit and later industry use.
- Prompt row projection now preserves `semantic_supplement`, so source-family bundle evidence does not disappear during compaction.

No-paid evidence:

- New mock + real-evidence artifact: `reports/r53_r60_p30_full_chain_ai_semis/p30_mock_semicap_role_specific_prompt_overlap_repair_20260703`.
- `agent_information_economy_audit.status=pass`.
- `agent_information_economy_audit.issue_counts={}`.
- `prompt_pack_overlap.overlap_detected=false`.
- `duplicate_prompt_evidence_ref_count=0`.
- `data_script_quality_audit.status=pass`.
- `agent_information_economy_preflight.status=pass`, one-case estimate remains `101400` tokens / `8` paid calls.
- The runner summary still has `gate_status=fail` and `diagnostic_only=true`, as expected for `--llm-backend mock`; this does not count as real memo-quality acceptance.

Verification:

```powershell
python -m compileall -q src/sec_agent/specialist_llm.py src/sec_agent/agent_information_economy.py
python -m pytest tests/test_multi_agent_specialist_llm.py tests/test_product_spec_pack.py tests/test_agent_information_economy.py -q
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_routing_fixtures.py tests/test_memo_logic_plan.py tests/test_multi_agent_contracts.py -q
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --case-catalog-path tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json --case-id fin_deep_semicap_asml_amat_lrcx_klac_cycle_025 --llm-backend mock --real-evidence-operators --output-dir reports/r53_r60_p30_full_chain_ai_semis --run-id p30_mock_semicap_role_specific_prompt_overlap_repair_20260703
```

Result:

- Targeted deterministic regression: `69 passed`.
- Runner / routing / MemoLogicPlan / contract regression: `131 passed`.
- No paid LLM call was made.

## Next

1. Treat `p30_paid_semicap_real_evidence_after_information_economy_guard_20260703_r1` as diagnostic: evidence / specialist path worked, but full-chain acceptance did not pass under the code that executed the paid run.
2. Do not launch the two-case AI/Semis batch as one paid run. Latest no-paid preflight still requires split one-case batches.
3. Treat Writer payload compression as repaired for the saved semicap artifact, but keep it under regression watch with `input_pack_fingerprint` metrics.
4. Treat specialist fanout ledger / route-selection repair and role-specific prompt-overlap repair as implemented deterministically, but keep them under fresh-artifact regression before any paid rerun.
5. If exact duplicate-token overlap becomes required for release gates, add opt-in prompt-token metering without persisting raw prompt text; current coverage is fingerprint-level only.
6. Run the next paid DeepSeek full-chain case only after data/script quality audit, AIE preflight, real-evidence preflight, specialist-fanout audit, role-specific prompt-overlap audit, and exact case-level token budget review all pass on a newly generated one-case artifact.
