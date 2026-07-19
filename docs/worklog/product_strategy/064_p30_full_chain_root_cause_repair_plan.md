# P30 Full-Chain Root-Cause Repair Plan

Date: 2026-07-01

Scope: record the seven repair tracks after the AI/Semis full-chain smoke, plus product-owner clarifications that every fail, gap, missing item, parser miss, writer miss, and weak evidence section must be root-caused. This is a repair plan before any broad 20-50 full-chain evaluation.

## Core Principle

The next repair round must not only add gates. A gate is diagnostic containment; the slice is not fixed until the earliest owned faulty artifact or contract is repaired.

Every failed required item, missing evidence path, parser miss, writer omission, raw numeric leak, or scope-hypothesis-only section must produce a typed root-cause row:

- `symptom_id`
- `case_id`
- `required_item_id`
- `affected_tickers`
- `earliest_faulty_artifact`
- `root_cause_layer`: `source_unavailable` / `source_locator` / `crawler_tool` / `parser` / `normalizer` / `retrieval_selector` / `pre_memo_fact_selection` / `memo_logic_plan` / `writer` / `renderer` / `eval_gate` / `workbench_projection`
- `owned_by_project`
- `repairability`
- `repair_action`
- `evidence_refs_or_attempt_refs`
- `why_not_external_gap`
- `verification_test`
- `status`

Only after this row exists may the system classify a problem as `public_source_absent`, `commercial_gap`, `parser_gap`, `pipeline_gap`, or `bounded_gap`.

## 1. Research Lead Required-Question Coverage Gate

Plan:

- Extend `ResearchObjectiveContract` with `required_question_items`.
- Each required item must state `question_item_id`, `dimension`, `required_tickers`, `required_evidence_roles`, `minimum_answer_status`, and `expected_repair_policy`.
- LeadReview must classify each required item as:
  - `answered`
  - `answered_with_boundary`
  - `retrievable_gap`
  - `bounded_public_gap`
  - `commercial_gap`
  - `pipeline_gap`
  - `not_material`
- If a final memo does not cover a required item, the case cannot pass.

Owner clarification:

- A missing required item is not enough. The system must record why it was missed:
  - Research Lead did not create the item.
  - Retrieval plan did not allocate a route.
  - Source route returned no candidates.
  - Parser could not structure the candidate.
  - Evidence selector dropped it.
  - MemoLogicPlan did not include it.
  - Writer ignored it.
  - Renderer removed it.
  - Eval failed to catch the omission.

Acceptance:

- NVDA/DELL must explicitly cover AI capex demand, supplier read-through, DELL product revenue, margin quality, customer/deployment evidence, competition, and counter-evidence.
- Semicap must explicitly cover orders/backlog, shipment cycle, capex cycle, customer concentration, export restrictions, and competitive position.
- Every non-covered item has a root-cause row and a repair/final-boundary decision.

## 2. ProductIntelligenceGraph To MemoLogicPlan Consumption

Plan:

- Convert existing ProductIntelligenceGraph rows into a `ProductReasoningFrame` for each company/family:
  - `product_profile`
  - `spec_architecture`
  - `product_kpi_exact`
  - `customer_deployment`
  - `performance_proxy`
  - `relationship_edges`
  - `financial_bridge`
- MemoLogicPlan must consume this frame before writer generation.
- Product sections must be organized around a reasoning chain rather than a flat list of facts:
  - AI infra: `GPU / AI server product -> architecture / generation -> customer deployment / channel -> supply chain -> margin / revenue impact`.
  - Semicap: `EUV / DUV / WFE / process control -> bookings / backlog -> customer capex -> export restriction -> cycle`.

Owner clarification:

- The system cannot say "product layer cannot judge because there is no SKU revenue" without explaining why SKU/product-level revenue is missing.
- Missing SKU revenue must be classified:
  - Company does not disclose SKU revenue.
  - Public free sources do not carry exact SKU revenue.
  - Commercial tracker needed.
  - Existing source likely has it but locator/parser missed it.
  - Evidence exists but selector/writer did not use it.
  - Product has no SKU-style economics and should use service/asset/operating slots instead.

Acceptance:

- Product analysis can still produce bounded product judgment using spec, architecture, deployment, channel, benchmark, supply-chain, and competitive evidence.
- Product-KPI exact remains strict; proxy evidence must not be promoted to revenue, shipment, ASP, share, or sell-through exact.
- Any "no SKU revenue" statement must link to a `sku_revenue_absence_reason` row.

## 3. Focus Ticker Evidence Coverage Gate

Plan:

- Add `FocusTickerCoverageMatrix` after `pre_memo_fact_selection`.
- For every focus ticker, check:
  - financial facts present
  - product/profile/spec/deployment/relationship facts present
  - gaps present
  - inclusion in MemoLogicPlan
  - inclusion in final memo
  - contradiction between selected facts and memo text

Owner clarification:

- If `pre_memo_fact_selection` has LRCX revenue/capex but the final memo says LRCX financial data is missing, failing the case is only containment. The required fix is finding why:
  - the selected fact was dropped during pack compression;
  - the fact was excluded by role quota;
  - MemoLogicPlan failed to carry it;
  - writer over-weighted a gap card;
  - renderer or answer compactor removed it;
  - the eval did not compare selected facts against final claims.

Acceptance:

- Every focus ticker has one of: `fact_used`, `fact_available_not_used_root_caused`, `bounded_gap`, `commercial_gap`, `not_material`.
- A memo cannot claim "no data" for a ticker/metric when approved selected facts exist.
- This gate must report earliest faulty artifact, not just `fail`.

## 4. Non-US / FPI / Local Disclosure Parser Depth

Plan:

- Add `NonUSDisclosureRoutePlan` for non-US and FPI issuers:
  - SEC FPI 20-F / 6-K
  - company IR quarterly results
  - annual report PDF
  - investor presentation
  - local exchange filing
  - company press release
- For ASML-like semicap issuers, targeted parser slots should include:
  - bookings
  - backlog
  - net sales
  - EUV / DUV
  - China exposure
  - system shipments
  - customer concentration where disclosed

Owner clarification:

- If the system can locate a filing/PDF/deck but cannot extract tables or numbers, it cannot directly close as `parser_gap` without root cause.
- The parser miss must classify why extraction failed:
  - file type unsupported;
  - PDF scanned image or table layout issue;
  - table parser failed;
  - language/locale/unit parsing failed;
  - source locator found wrong document;
  - crawler downloaded partial/truncated content;
  - tool/browser route failed;
  - agent selected the wrong section;
  - source contains text but no target metric;
  - company genuinely does not disclose the target metric.

Acceptance:

- `parser_gap` rows must include `parser_failure_reason`.
- `public_source_absent` is allowed only after official source lookup and parser attempts prove no target disclosure exists.
- ASML cannot stop at "6-K exists"; it must either extract relevant facts or produce a root-caused locator/parser/source-boundary row.

## 5. Numeric Display Lineage And Missing-Value Hard Fail

Plan:

- Introduce `DisplayValueLineage` before writer:
  - `raw_value`
  - `normalized_value`
  - `display_value`
  - `unit`
  - `scale`
  - `period`
  - `sign_policy`
  - `source_citation`
- Memo Writer may use only `display_value` for user-facing numeric text.
- Renderer / memo gate must hard-fail:
  - raw numeric in direct answer without unit/period;
  - bare value-year tuple such as `(151003, 2026)`;
  - sentence patterns such as `达到 [C10]` with no value;
  - amount without unit or period;
  - raw `usd_thousands` not converted into readable scale.

Owner clarification:

- If a raw numeric is valid but no `display_value` exists, the bug must be root-caused:
  - normalizer did not infer scale;
  - display formatter skipped the metric family;
  - period/unit metadata was missing;
  - fact passed selection without display lineage;
  - writer was given raw fact fields despite display contract;
  - renderer bypassed display-value contract.

Acceptance:

- No user-facing number appears without display lineage.
- Valid raw numeric facts missing `display_value` become `display_lineage_missing` root-cause rows, not silent writer omissions.
- Missing-value sentences are hard failures and point to the exact claim/fact/citation that caused them.

## 6. Relationship Graph Authority Downgrade And Explanation

Plan:

- Assign explicit authority type to each relationship edge:
  - `navigation_edge`
  - `scope_hypothesis`
  - `parser_backed_relationship`
  - `official_relationship`
  - `deployment_signal`
  - `supply_chain_signal`
- MemoLogicPlan may use `scope_hypothesis` for navigation and bounded context only.
- `scope_hypothesis` cannot satisfy orders, backlog, shipment, revenue, share, customer concentration, export restriction, or causal read-through requirements by itself.

Owner clarification:

- If a section mainly uses `scope_hypothesis`, the system must explain why stronger evidence is absent:
  - route not allocated;
  - source role exists but company lacks data;
  - parser failed;
  - product/source lane coverage claim was stale or too broad;
  - source authority mart has only navigation edges;
  - commercial tracker needed;
  - Research Lead did not trigger repair.
- This is especially important because AI/Semis data coverage was previously marked broadly complete. A scope-only section may indicate stale coverage accounting or a pack-consumption defect.

Acceptance:

- A section dominated by `scope_hypothesis` must become `low_confidence_context` and create a `why_scope_only` root-cause row.
- If a stronger edge exists but was not selected, the fix is selector/pack/writer repair.
- If no stronger public source exists, record public-source boundary with source attempts.

## 7. Product-Quality Eval Upgrade

Plan:

Add product-quality gates:

- `RequiredQuestionCoverageGate`
- `FocusTickerCoverageGate`
- `NumericDisplayGate`
- `MissingValueSentenceGate`
- `EvidenceRoleAuthorityGate`
- `ProductReasoningDepthGate`
- `WorkbenchProjectionGate`
- `TokenEfficiencyGate`
- `RootCauseCompletenessGate`

Owner clarification:

- The eval gate must not only reject the bad output; it must require the diagnostic row that explains the bad output.
- "No evidence" claims must be checked against selected facts, retrieval results, source attempts, parser attempts, and known pack coverage.
- Token inefficiency must identify whether the waste is caused by specialist over-activation, redundant verification, oversized payload, weak compression, writer retries, or low claim yield.

Acceptance:

- A case can only pass product-quality eval when each failed or bounded item has root-cause attribution.
- Broad full-chain eval remains blocked until the two AI/Semis regression cases pass the new gates.
- Passing `gate_status=pass` while `diagnostic_only=true` is not PRD/product acceptance.

## Repair Order

1. [x] Fix `DisplayValueLineage` and missing-value hard fail.
2. [x] Add required-question and focus-ticker coverage matrices with root-cause rows.
3. [x] Wire ProductIntelligenceGraph into MemoLogicPlan as a required ProductReasoningFrame.
4. [x] Downgrade relationship scope-hypothesis authority and add `why_scope_only` root-cause rows.
5. [x] Repair ASML/FPI/non-US disclosure route and parser diagnosis.
6. [x] Upgrade eval gates to require product-quality and root-cause completeness.
7. [x] Re-run the two AI/Semis cases only after deterministic tests pass.

## 2026-07-02 Implementation Status

Deterministic repair implementation is complete before real-LLM reruns:

- `DisplayValueLineage` now attaches `display_value`, `display_value_lineage`, and `display_lineage_status` to approved facts and derived metrics in `pre_memo_fact_selection`. Numeric approved facts without display lineage fail validation before writer visibility.
- Deterministic ClaimCards now use `display_value`, including scaled currency display such as `usd_millions -> $B`, and no longer expose raw capex sign/scale tuples in user-facing claim text.
- Memo Writer compact payloads now expose display fields, not raw `value`, for financial line items, product KPIs, and peer comparisons; the writer prompt requires user-facing numbers to come from display fields.
- MemoLogicPlan now carries a `product_reasoning_frame` with product profile/spec/KPI/deployment/proxy/relationship/scope-hypothesis refs. Product sections validate that this frame is present.
- LangGraph Research Lead paths now build a ProductReasoningFrame from selected judgment claims, context rows, dimension portfolio, ProductSpec pack, relationship observation, and source authority coverage before Memo Writer.
- Full-chain eval now writes `p30_root_cause_quality_audit.json` per case and includes a hard `p30_root_cause_quality` layer for P30 / AI infra / semicap cases.
- The P30 audit now checks required item coverage, focus-ticker selected-fact-vs-memo contradictions, raw unitless numeric leaks, missing-value sentence patterns, product frame presence, scope-hypothesis dominance, ASML/FPI official-source parser diagnosis, and root-cause row completeness.
- Run-audit DB relative paths now resolve against repo root instead of the case artifact directory.

Deterministic tests passed:

```text
python -m py_compile src/sec_agent/d_series_fact_selection.py src/sec_agent/memo_logic_plan.py src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
python -m pytest tests/test_d_series_fact_selection.py tests/test_memo_logic_plan.py tests/test_multi_agent_real_llm_chain_eval.py -q
61 passed
```

R2 rerun exposed that item 5 was not complete under the new standard: ASML official SEC/FPI/IR/product sources were reachable, but the row/claim chain only said "context reached / no exact fact promoted" and did not carry a machine-readable parser diagnosis. The fix now writes parser diagnosis at the earliest source row and preserves it through Lead targeted-repair ClaimCards, MemoLogicPlan repair summaries, writer compact payloads, and P30 audit:

- `source_attempt_outcome`
- `source_route_diagnosis`
- `source_specific_parser_status`
- `exact_fact_parser_failure_reason`
- `parser_failure_reason`
- `why_no_exact_fact_promoted`
- `next_parser_action`
- `parser_diagnosis_complete`

Updated deterministic tests passed:

```text
python -m py_compile src/sec_agent/official_issuer_repair.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/memo_logic_plan.py src/sec_agent/memo_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
python -m pytest tests/test_runtime_bridge_contracts.py::test_official_issuer_repair_materializes_asml_sec_context_without_promoting_exact_fact tests/test_multi_agent_real_llm_chain_eval.py::test_p30_non_us_official_source_gap_requires_parser_diagnosis tests/test_multi_agent_real_llm_chain_eval.py::test_p30_non_us_official_source_gap_fails_without_parser_diagnosis -q
python -m pytest tests/test_d_series_fact_selection.py tests/test_memo_logic_plan.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_runtime_bridge_contracts.py tests/test_public_web_gap_repair.py -q
138 passed
```

R3 full-chain rerun completed after deterministic tests. Both AI/Semis cases passed the new P30 root-cause audit, but the run remains `diagnostic_only=true` because output-density and token-efficiency gates still found product-quality issues.

Command:

```text
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --case-catalog-path tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json --case-id fin_deep_ai_infra_nvda_dell_capex_023 --case-id fin_deep_semicap_asml_amat_lrcx_klac_cycle_025 --output-dir eval/sec_cases/outputs/p30_root_cause_repair_full_chain/20260702_p30_root_cause_repair_ai_semis_r3 --run-id 20260702_p30_root_cause_repair_ai_semis_r3 --llm-backend deepseek --base-url https://api.deepseek.com --chat-completions-path /chat/completions --model deepseek-v4-pro --api-key-env DEEPSEEK_API_KEY --real-evidence-operators --context-runner in_process --bge-device cuda --evidence-operator-fanout-workers 1 --reranker-batch-size 8 --strict
```

Result:

- `gate_status=pass`
- `case_count=2`, `passed=2`, `failed=0`, `pass_rate=1.0`
- `p30_root_cause_quality_audit.status=pass` for both cases
- `root_cause_rows=0` for both cases
- P30 checks all true: required items covered, focus-ticker no-evidence contradiction absent, display lineage complete, no raw unitless numeric, no missing-value claim, product reasoning frame present, scope-hypothesis not used as primary product proof, ASML/FPI parser diagnosis complete.
- `diagnostic_only=true` remains because output-quality audit reports `high_total_token_cost`, `memo_writer_high_token_cost`, `low_claim_card_token_efficiency`, `low_rendered_claim_token_efficiency`, and `low_memo_chars_per_token`.

New root-cause work exposed by R3:

- Memo still does not convert the expensive upstream payload into dense analyst judgment. It answers more safely than before, but still spends too many tokens per supported claim.
- AI infra case still overuses general demand-pool framing. It cites cloud capex and DELL/NVDA facts, but the writer needs stronger read-through organization from `cloud capex -> GPU/server procurement -> supplier revenue/margin`.
- Semicap case no longer falsely says ASML/FPI source is absent, but it still leans on industry-scope context when orders/backlog/export/customer concentration are not extracted. That is now a known evidence-depth/productization issue, not a hidden source-absence claim.
- Product section quality is improved by ProductReasoningFrame, but the writer still needs a stronger thesis-led contract so product specs/deployment/relationships are used as reasoning spine, not appended evidence.

## Decision

Do not run broad 20-50 full-chain cases yet. The seven root-cause repair items are fixed enough for the two AI/Semis cases to pass the P30 root-cause audit, but product acceptance is still blocked by token-to-insight efficiency and memo reasoning density. The next slice should repair claim-yield / MemoLogicPlan-to-writer compression / thesis-led rendering before broad evaluation.

## 2026-07-02 R4-R6 Root-Cause Follow-Up

R4/R5 exposed that the previous "seven items fixed" statement was still too coarse. The P30 audit passed in R3, but upstream-owned defects remained:

- Deep-research memo compaction capped supported claims too aggressively, so exact product/capex facts were dropped behind weaker context claims.
- `pre_memo_fact_selection` allowed percent/change rows to enter `product_kpi:product_revenue`, producing user-facing errors such as `Total ISG net revenue of 24%`.
- `financial_metric:gross_margin` accepted an impossible `2,802%` rate from a parser/unit mismatch instead of rejecting it as an owned metric-unit conflict.
- Reapplying pre-memo selection was not idempotent: stale `pre_memo_fact_selector` ClaimCards could survive repair/replay and contaminate the writer payload.
- MemoLogicPlan validation rejected sections even when the section itself carried gap refs, because it only looked at LeadReview-owned gap ids.
- Dimension states could keep false missing-capex gap language even after supported capex claims existed for the same tickers.

Additional repairs now implemented:

- `src/sec_agent/memo_llm.py` raises deep-research claim budgets and rank-balances exact product/capex facts before context fillers; ticker balancing now counts single-ticker factual claims instead of treating multi-ticker thesis text as coverage.
- `src/sec_agent/d_series_fact_selection.py` rejects `product_kpi:product_revenue` percent/change rows, rejects out-of-bounds gross-margin rates, adds display-lineage-backed claim text, prioritizes exact prompt-matched product lines and recent periods, and rebuilds deterministic fact ClaimCards idempotently.
- `src/sec_agent/memo_logic_plan.py` accepts dimension-owned `gap_ids` / `gap_refs` as valid section trace when LeadReview does not own the gap id.
- `src/sec_agent/multi_agent_contracts.py` strips/resolves false missing-metric dimension text when supported claims already contain the matching metric/ticker facts.
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` adds P30 checks for MemoLogicPlan validation failure and product-evidence contradiction.

Verification:

```text
python -m pytest tests/test_d_series_fact_selection.py tests/test_multi_agent_memo_llm_repair.py tests/test_memo_logic_plan.py tests/test_multi_agent_contracts.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_output_quality_audit.py -q
165 passed

python -m py_compile src/sec_agent/d_series_fact_selection.py src/sec_agent/memo_llm.py src/sec_agent/memo_logic_plan.py src/sec_agent/multi_agent_contracts.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py scripts/eval_multi_agent/audit_multi_agent_output_quality.py
```

R6 full-chain rerun:

```text
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --case-catalog-path tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json --case-id fin_deep_ai_infra_nvda_dell_capex_023 --case-id fin_deep_semicap_asml_amat_lrcx_klac_cycle_025 --output-dir eval/sec_cases/outputs/p30_root_cause_repair_full_chain/20260702_p30_claim_yield_selector_plan_trace_ai_semis_r6 --run-id 20260702_p30_claim_yield_selector_plan_trace_ai_semis_r6 --llm-backend deepseek --base-url https://api.deepseek.com --chat-completions-path /chat/completions --model deepseek-v4-pro --api-key-env DEEPSEEK_API_KEY --real-evidence-operators --context-runner in_process --bge-device cuda --evidence-operator-fanout-workers 1 --reranker-batch-size 8 --strict
```

R6 result:

- Summary `gate_status=pass`, `case_count=2`, `passed=2`, `failed=0`, `pass_rate=1.0`, `total_tool_calls=25`.
- Both cases have `p30_root_cause_quality_audit.status=pass`.
- Surface readability and investment-quality gates pass for both cases.
- The AI infra writer payload now includes NVDA gross margin, DELL AI-optimized servers revenue, AMZN/GOOGL/MSFT capex, and DELL capex without the previous `24%` / `2,802%` numeric errors.
- The semicap case no longer loses LRCX financial facts or fails MemoLogicPlan trace validation.

R6 is still not PRD/product acceptance:

- Summary remains `diagnostic_only=true`.
- Manual rendered-output inspection still finds weak analyst style: sections include generic "current evidence boundary" phrasing, some sentences describe how to judge rather than making a sharper bounded judgment, and semicap still underuses ASML orders/backlog/export/customer concentration as mainline evidence.
- `diagnostic_quality_audit.required=false` for these cases, so the current automated gate is still not strict enough to catch every memo-depth issue.

Next blocker before broad 20-50:

- Upgrade thesis-led MemoLogicPlan / writer contract so each required item has an answer-first judgment, evidence bridge, counter-read, and "what would change the view" before rendering.
- Add product/semicap playbook-specific required items for AI infra and semicap: cloud capex read-through, GPU/server procurement, AI server margin quality, semicap bookings/backlog, customer concentration, export controls, and cycle position.
- Make output-quality eval fail generic boundary-heavy sections even when citation and hallucination gates pass.

## 2026-07-02 R7 Thesis-Led Required-Item Answer Plan

R7 closes the deterministic part of the next blocker above. The fix is deliberately upstream of the final output gate: MemoLogicPlan now has to tell the writer how each required item should be answered, instead of handing over a broad claim inventory and hoping the writer infers the logic.

Implemented:

- `MemoLogicPlan.required_item_answer_plan` is generated for every `required_question_items` row.
- Each required item now carries an answer contract:
  - present bounded judgment;
  - evidence bridge;
  - counter-read;
  - what would change the view.
- AI infra contracts cover DELL AI server quality / margin bridge, NVDA GPU supply generation, cloud capex read-through, and customer deployment or order signal.
- Semicap contracts cover ASML orders/backlog, shipment/cycle context, customer concentration/deployment, and export restriction context.
- Writer compact payload now includes `required_item_answer_plan` and per-section `required_item_answer_moves`; the prompt tells Memo Writer to execute these answer plans rather than repeat gap language.
- P30 required-item eval now distinguishes:
  - `covered`;
  - `term_only_or_boundary_only`;
  - `available_not_rendered`;
  - `missing_or_not_selected`.
- If the final memo only mentions a term and then says "needs verification / current evidence boundary", the root cause is now assigned to `memo_writer_required_item_answer_execution` or `memo_logic_plan_required_item_answer_projection`, not hidden as a public-source gap.
- Output-quality audit now flags `memo_surface_boundary_heavy_or_noncommittal` when final prose is dominated by "current evidence boundary / needs verification / cannot conclude" style language.

Verification:

```text
python -m py_compile src/sec_agent/memo_logic_plan.py src/sec_agent/memo_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py scripts/eval_multi_agent/audit_multi_agent_output_quality.py
python -m pytest tests/test_memo_logic_plan.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_output_quality_audit.py -q
70 passed
```

Current status:

- Deterministic/root-cause repair for thesis-led required-item planning is complete.
- Full-chain R7 rerun is still pending; broad 20-50 remains blocked until the two AI/Semis cases prove the writer actually uses this contract to produce sharper bounded judgments.
- This is not a fallback-only gate. The gate exists to catch regression, but the upstream repaired artifact is `MemoLogicPlan -> compact writer payload -> required-item answer execution`.

## 2026-07-02 R8-R13 Economic-Role And FPI Route Follow-Up

R8-R13 continued the same repair order instead of opening broad eval. Two owned issues were found after the thesis-led answer-plan work:

- Public product/external proxy rows without an exact source role could still be selected or salvaged into memo prose as if they supported product revenue, order, backlog, or customer-demand claims.
- The P30 economic-role audit used overly broad text windows. Correct boundary language such as "DELL capex is issuer own capacity investment, not direct customer demand" could be falsely flagged as capex-to-demand misuse.
- FPI issuers such as ASML could have 6-K presence in the manifest, while a requested 10-Q/8-K route still produced a false `source_coverage_gap` instead of treating 6-K as the interim FPI route.

Repairs implemented:

- `src/sec_agent/memo_llm.py` now demotes public proxy rows that lack an economic/source role; salvage prose must state that such rows are only product/official/external leads and cannot be promoted to product revenue, orders, backlog, or customer demand.
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` now checks economic-role misuse at sentence/chunk level and ignores explicit negation/boundary clauses such as "not direct customer demand" or "cannot treat capex as supplier revenue".
- `src/sec_agent/mcp_tool_registry.py` now treats FPI forms as route equivalents for manifest/source coverage: `20-F/40-F` can satisfy annual-report scope and `6-K` can satisfy interim/event scope; `6-K` routes through `8k_commentary` and no longer leaves a false source gap when available.

Verification:

```text
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_salvage_public_proxy_without_role_is_not_rendered_as_product_revenue tests/test_multi_agent_memo_llm_repair.py::test_memo_supported_claim_selection_demotes_unroled_public_proxy_below_exact_role_fact tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_flags_economic_role_misuse tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_investment_quality_allows_role_boundary_opening -q
4 passed

python -m pytest tests/test_sec_agent_mcp_runtime_tools.py::test_mcp_registry_uses_fpi_6k_as_interim_route_without_false_sec_gap tests/test_sec_agent_mcp_runtime_tools.py::test_mcp_registry_returns_source_gap_when_manifest_scope_has_no_available_filings tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_flags_economic_role_misuse tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_allows_capex_customer_demand_boundary_language -q
4 passed

python -m pytest tests/test_d_series_fact_selection.py tests/test_memo_logic_plan.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_sec_agent_10q_source_contract.py -q
188 passed

python -m py_compile src/sec_agent/memo_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py src/sec_agent/d_series_fact_selection.py src/sec_agent/memo_logic_plan.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/mcp_tool_registry.py
```

R13 full-chain rerun:

```text
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --case-catalog-path tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json --case-id fin_deep_ai_infra_nvda_dell_capex_023 --case-id fin_deep_semicap_asml_amat_lrcx_klac_cycle_025 --output-dir eval/sec_cases/outputs/p30_root_cause_repair_full_chain/20260702_p30_required_item_answer_plan_ai_semis_r13 --run-id 20260702_p30_required_item_answer_plan_ai_semis_r13 --llm-backend deepseek --base-url https://api.deepseek.com --chat-completions-path /chat/completions --model deepseek-v4-pro --api-key-env DEEPSEEK_API_KEY --real-evidence-operators --context-runner in_process --bge-device cuda --evidence-operator-fanout-workers 1 --reranker-batch-size 8 --strict
```

R13 result is diagnostic-only and not a closeout:

- Initial summary failed both cases: AI infra failed `p30_root_cause_quality.economic_role_no_misuse`; semicap failed specialist/memo checks and loop-break `repair_no_progress`.
- AI infra failure was traced to the audit false positive above. After the audit repair, rescoring the same rendered memo returns no economic-role misuse rows and investment-quality checks pass.
- Semicap failure cannot be counted as a product/data judgment because DeepSeek returned `HTTP 402 Insufficient Balance` during specialist calls. The run is therefore provider-blocked, not a valid semicap product-quality pass/fail.
- The FPI/6-K route issue is fixed deterministically, but semicap still requires a fresh provider-healthy full-chain rerun before broad 20-50 is allowed.

Current boundary:

- Deterministic P30 root-cause repairs for display lineage, product frame, required-item answer plan, economic-role misuse, public proxy no-role, and FPI/6-K route coverage are implemented and tested.
- Broad 20-50 remains blocked. Required next evidence is a new two-case AI/Semis full-chain rerun under a provider account with sufficient balance, followed by manual rendered-output inspection and Workbench artifact projection check.

## 2026-07-02 R14 Token Budget And Specialist Cost Root-Cause Repair

User review after R13 correctly identified that the next repair cannot start by rerunning paid full-chain cases. The owned cost issues must be fixed first:

1. Full-chain regression was run too often when deterministic / node-level tests could verify most repairs.
2. Specialist fanout was too broad for AI/Semis cases and activated agents by generic deep-research shape rather than by required items.
3. Specialist inputs were too fat because large upstream packs were passed into each agent with insufficient role-specific compaction.
4. Claim yield was too low: too many tokens did not become rendered memo claims or bounded judgments.
5. There was no hard token budget gate before model calls by node / case / run.

Product-level upgrade:

This item is no longer only a cost-control or provider-budget issue. It is a core measure of agent framework quality: `Agent Information Economy`. A good financial research agent should minimize useless information transfer and maximize conversion from evidence/context into judgments, gaps, counters, and workpaper artifacts. If the system spends a large number of tokens and produces a shallow memo, that is evidence of an architecture defect, not merely an expensive run.

The five symptoms map to framework defects:

- full-chain rerun too many -> missing deterministic / node-level debugging discipline;
- specialist fanout too broad -> Research Lead planning and required-item routing are too weak;
- specialist input too fat -> context compression and role-specific selection are insufficient;
- claim yield too low -> specialist / LeadReview / writer contracts are not converting evidence into analyst output;
- missing budget gate -> runtime lacks pre-call governance and cannot stop waste before provider spend.

Repair policy:

- Paid full-chain is now last-step evidence only. It must be preceded by deterministic tests, node-level tests, and a token-budget preflight.
- A broad 20-50 full-chain run is still blocked. It cannot be used to "discover" problems that can be isolated by parser, selector, specialist, MemoLogicPlan, writer-payload, or eval unit tests.
- Full-chain eval must write a token-budget plan and block before model calls when estimated run / case / paid-call budgets are exceeded.
- Specialist activation must be tied to required-question items, explicit user intent, or visible exact/core evidence. Generic deep-research scope cannot activate every specialist.
- Specialist prompts must consume compact role-specific packs. Raw ProductSpecPack / CapitalMacroPack / FundamentalStatementPack / FundamentalPeerStatementPanel cannot be duplicated across every specialist without prompt-budget caps.
- Claim-yield and output-cost quality flags are blocking diagnostics. If token cost is high and rendered claims are low, the run is not a product-quality pass even when hallucination/safety gates pass.
- Token/cost diagnostics must identify the earliest owned root cause: planning, routing, selector, compression, specialist analysis, repair loop, LeadReview, MemoLogicPlan, or writer surface. They cannot stop at "over budget."

Implemented gate targets:

- `full-chain rerun too many` -> token-budget preflight supports `--token-budget-preflight-only` and blocks non-preflight paid runs before graph/model construction when budget is exceeded.
- `specialist fanout too broad` -> required-item specialist activation gate is default-on.
- `specialist input too fat` -> role-specific compact prompt pack wrappers are default-on for product, capital, fundamental, and peer-statement packs.
- `claim yield too low` -> output-cost quality gate fails runs with high token cost, low rendered-claim efficiency, low memo chars per token, specialist low-yield, or all-specialists-active patterns.
- `missing hard token budget gate` -> run/case/paid-call token budget plan is written as an artifact and returned in aggregate summary.

Verification so far is intentionally no-paid:

```text
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_output_quality_audit.py -q
122 passed

python -m pytest tests/test_multi_agent_contracts.py tests/test_memo_logic_plan.py tests/test_multi_agent_memo_llm_repair.py -q
93 passed

python -m compileall -q src/sec_agent/specialist_llm.py src/sec_agent/multi_agent_runtime.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
```

No DeepSeek / paid full-chain run was executed for R14.

Budget preflight on the two AI/Semis cases now blocks before model calls:

```text
status=blocked_preflight_token_budget
estimated_total_tokens=272000
estimated_paid_call_count=18
token_budget_total=180000
token_budget_per_case=120000
max_paid_calls=8
violations=run_token_budget_exceeded, paid_call_budget_exceeded, per_case_token_budget_exceeded
```

Current boundary:

- R14 closes the first cost-control root causes enough to prevent another accidental token burn.
- It does not prove memo quality is fixed; it prevents paying for another memo-quality run until the deterministic/node-level surfaces fit the budget.
- Next full-chain attempt must first reduce the estimated two-case budget or be explicitly approved with `--allow-expensive-llm`.
- Product acceptance remains blocked until token-to-insight metrics prove the agent framework is producing useful workpaper/judgment artifacts from its context, not just staying under a spend cap.
