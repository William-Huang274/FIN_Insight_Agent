# P30 Root-Cause Repair Implementation

Date: 2026-07-02

## Prompt

Implement repair order 1-7 from `064_p30_full_chain_root_cause_repair_plan.md`. Do not hide owned defects behind fallback gates. Fix the six deterministic/root-cause tracks first, then rerun the two AI/Semis full-chain cases and report new issues.

## Decisions

- Treat display-value generation as an upstream data contract, not a writer style issue.
- Treat selected-fact-vs-memo contradictions as owned pipeline defects until the earliest faulty artifact is identified.
- Product analysis must consume a ProductReasoningFrame. Missing SKU revenue cannot suppress spec, architecture, deployment, channel, performance proxy, or relationship evidence.
- Scope-hypothesis relationship edges are navigation/context only. If they dominate a product section, the case must emit a `why_scope_only` root-cause row.
- ASML/FPI official-source presence without promoted facts is a parser/locator diagnosis item, not an automatic public-source-absent gap.

## Work Completed

- Added deterministic `DisplayValueLineage` generation in `src/sec_agent/d_series_fact_selection.py`.
- Changed deterministic fact ClaimCards to use `display_value` instead of raw `value`.
- Added validation failures for numeric approved facts or derived metrics missing display values.
- Changed `src/sec_agent/memo_llm.py` compact payloads and prompt so Memo Writer uses display fields only.
- Added `product_reasoning_frame` to `src/sec_agent/memo_logic_plan.py`.
- Wired ProductReasoningFrame construction into both Research Lead memo-plan paths in `src/sec_agent/langgraph_orchestrator.py`.
- Added P30 root-cause audit to `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
- Fixed full-chain run-audit DB path resolution so relative paths resolve from repo root.
- Added deterministic regression tests for display-value lineage, P30 raw numeric leakage, selected-fact-vs-memo contradiction, and scope-hypothesis-only product proof.
- Fixed Memo Writer zh-CN repair/localization so English-heavy fragments inside otherwise Chinese fields are translated instead of causing deterministic memo verification fallback to `Bounded answer only`.
- Added ASML/FPI parser-diagnosis fields at source-row level in `official_issuer_repair`, including exact-value parser status, parser failure reason, why no exact fact was promoted, and next parser action.
- Preserved those ASML/FPI diagnostics through Research Lead targeted-repair ClaimCards, MemoLogicPlan repair summaries, and Memo Writer compact payloads.
- Changed P30 audit so ASML official-source reachability without exact facts only passes when parser diagnosis is complete; official-source reachability without parser diagnosis still fails.

## Evidence

Commands run:

```text
python -m py_compile src/sec_agent/d_series_fact_selection.py src/sec_agent/memo_logic_plan.py src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
python -m pytest tests/test_d_series_fact_selection.py tests/test_memo_logic_plan.py tests/test_multi_agent_real_llm_chain_eval.py -q
```

Result:

```text
Initial repair set: 61 passed
Updated P30 repair set: 138 passed
```

## Next Step

R3 completed the two AI/Semis full-chain regression cases:

- `fin_deep_ai_infra_nvda_dell_capex_023`
- `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025`

The expected output was not merely pass/fail. Each failure would have required `p30_root_cause_quality_audit.root_cause_rows` with the earliest faulty artifact, owner layer, repair action, and verification test. R3 produced no P30 root-cause rows because the targeted P30 checks passed.

## R2 Findings And Fixes

R2 full-chain rerun still failed both cases, but for narrower owned reasons:

- `fin_deep_ai_infra_nvda_dell_capex_023`: Memo Writer produced an English-heavy `counter_read` inside a zh-CN field. The deterministic verifier rejected the memo and fallback rendered `Bounded answer only`. Root cause was localization/repair logic, not evidence absence. Fixed by detecting English-heavy fragments after Chinese wrapping and translating common memo fragments before verification.
- `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025`: Required items and raw numeric checks were repaired, but ASML/FPI parser diagnosis remained incomplete. Official ASML SEC/FPI/IR/product surfaces were reachable, yet the row/claim chain did not explain whether the gap was filing-document fetch, table parsing, or exact-value promotion. Fixed by adding source-row parser diagnosis and requiring P30 to see that diagnosis before accepting the boundary.

Updated deterministic evidence:

```text
python -m py_compile src/sec_agent/official_issuer_repair.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/memo_logic_plan.py src/sec_agent/memo_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
python -m pytest tests/test_runtime_bridge_contracts.py::test_official_issuer_repair_materializes_asml_sec_context_without_promoting_exact_fact tests/test_multi_agent_real_llm_chain_eval.py::test_p30_non_us_official_source_gap_requires_parser_diagnosis tests/test_multi_agent_real_llm_chain_eval.py::test_p30_non_us_official_source_gap_fails_without_parser_diagnosis -q
python -m pytest tests/test_d_series_fact_selection.py tests/test_memo_logic_plan.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_runtime_bridge_contracts.py tests/test_public_web_gap_repair.py -q
138 passed
```

## Safety Notes

- No secrets were written to disk.
- Existing unrelated dirty worktree files were not reverted.
- Broad 20-50 case eval remains blocked, not because P30 root-cause audit still fails, but because R3 exposed token-to-insight and thesis-led memo density issues that would make broad eval wasteful before repair.

## R3 Full-Chain Rerun

Command:

```text
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --case-catalog-path tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json --case-id fin_deep_ai_infra_nvda_dell_capex_023 --case-id fin_deep_semicap_asml_amat_lrcx_klac_cycle_025 --output-dir eval/sec_cases/outputs/p30_root_cause_repair_full_chain/20260702_p30_root_cause_repair_ai_semis_r3 --run-id 20260702_p30_root_cause_repair_ai_semis_r3 --llm-backend deepseek --base-url https://api.deepseek.com --chat-completions-path /chat/completions --model deepseek-v4-pro --api-key-env DEEPSEEK_API_KEY --real-evidence-operators --context-runner in_process --bge-device cuda --evidence-operator-fanout-workers 1 --reranker-batch-size 8 --strict
```

Result:

```text
gate_status=pass
diagnostic_only=true
case_count=2
passed=2
failed=0
pass_rate=1.0
total_tool_calls=23
```

Per-case P30 audit:

- `fin_deep_ai_infra_nvda_dell_capex_023`: `p30_root_cause_quality_audit.status=pass`, `root_cause_rows=0`, all P30 checks true.
- `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025`: `p30_root_cause_quality_audit.status=pass`, `root_cause_rows=0`, all P30 checks true.

Output-quality audit still reports:

- `high_total_token_cost=2`
- `memo_writer_high_token_cost=2`
- `low_claim_card_token_efficiency=2`
- `low_rendered_claim_token_efficiency=2`
- `low_memo_chars_per_token=2`

Manual rendered-output inspection:

- The AI infra memo is no longer a fallback or "cannot judge" answer, but still organizes too much around generic demand-pool evidence. It cites cloud capex, DELL product revenue, NVDA data center growth, and DELL AI server revenue, yet the read-through from cloud capex to DELL/NVDA revenue and margin quality is still not strong enough.
- The semicap memo no longer falsely treats ASML/FPI disclosure as absent, but it still cannot extract ASML orders/backlog/export/customer concentration into strong facts. It correctly treats sector-depth rows as context, but the final memo remains thin for bookings/backlog/customer concentration.
- The writer produces readable zh-CN, but some sentence-level phrasing remains weak or awkward, for example over-generic "投资判断应先看..." structures and thesis guidance that describes how to judge instead of taking a sharper bounded view.

Next root-cause target:

- Reduce specialist / verifier / writer payload duplication.
- Make MemoLogicPlan hand the writer a small, thesis-led structure rather than a broad claim inventory.
- Add claim-yield diagnostics that explain which activated specialists produced no memo-useful ClaimCards.
- Add writer-density acceptance: broad evaluation should require supported insight density, not only absence of hallucination or missing-value defects.

## R4-R6 Claim-Yield And Numeric-Lineage Repair

After R3, a closer artifact review found that several owned upstream defects still existed even though the P30 root-cause audit passed. The follow-up repair did not add a weak fallback; it fixed the earliest faulty artifacts.

Root causes found:

- R4/R5 deep-research compacting selected too few supported claims after thesis pack activation, so exact product and capex facts could be dropped behind context rows.
- DELL product revenue candidates contained `percent` rows from MD&A change columns; these were still approved as `product_kpi:product_revenue` and could render as `Total ISG net revenue of 24%`.
- A DELL gross-margin row carried `numeric_value=2802` and `unit=percent`, producing `2,802%`; this is a parser/unit conflict, not a valid margin fact.
- `apply_pre_memo_fact_selection_to_judgment` was not idempotent; stale `pre_memo_fact_selector` ClaimCards survived repair/replay and polluted the writer payload.
- MemoLogicPlan section validation did not count dimension-owned gap refs as valid trace, causing avoidable validation failures.
- Dimension states could retain "missing capex" text after supported capex facts for the same ticker/metric were available.

Implementation:

- `src/sec_agent/memo_llm.py`
  - Raised deep-research supported-claim caps when thesis packs are ready.
  - Added selection penalties for missing-data / scope-hypothesis context rows.
  - Prioritized `company_reported_product_operating_fact` and `company_reported_financial_fact`.
  - Added dimension, capex, and ticker balancing; ticker balancing now uses single-ticker factual coverage, not multi-ticker thesis text.
- `src/sec_agent/d_series_fact_selection.py`
  - Rejects percent/change rows for `product_kpi:product_revenue` and `financial_metric:revenue`.
  - Rejects out-of-bounds gross-margin rates and metric/unit mismatches before memo eligibility.
  - Adds display lineage to approved facts and derived metrics.
  - Prioritizes exact product phrase matches and more recent periods.
  - Rebuilds deterministic `pre_memo_fact_selector` ClaimCards idempotently on every selection application.
- `src/sec_agent/memo_logic_plan.py`
  - Accepts section-owned `gap_ids` / `gap_refs` as valid trace when LeadReview did not emit the gap id.
- `src/sec_agent/multi_agent_contracts.py`
  - Removes or strips resolved false missing-metric dimension statements when supported claims already contain the same ticker/metric facts.
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - Adds P30 audit rows/checks for MemoLogicPlan validation failure and "memo says product evidence is absent despite available product evidence."

Deterministic verification:

```text
python -m pytest tests/test_d_series_fact_selection.py tests/test_multi_agent_memo_llm_repair.py tests/test_memo_logic_plan.py tests/test_multi_agent_contracts.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_output_quality_audit.py -q
165 passed

python -m py_compile src/sec_agent/d_series_fact_selection.py src/sec_agent/memo_llm.py src/sec_agent/memo_logic_plan.py src/sec_agent/multi_agent_contracts.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py scripts/eval_multi_agent/audit_multi_agent_output_quality.py
```

Offline projection from the R5 ledger now rejects the bad DELL rows:

- `revenue_percent_or_change_not_exact_revenue_memo_eligible`: 5 DELL product revenue percent/change rows.
- `gross_margin_rate_out_of_bounds_not_memo_eligible`: 1 DELL gross-margin parser/unit conflict row.
- Selected deep-research payload contains `DELL AI-optimized servers $16.1B` instead of `Total ISG net revenue 24%`.

R6 full-chain result:

```text
gate_status=pass
diagnostic_only=true
case_count=2
passed=2
failed=0
pass_rate=1.0
total_tool_calls=25
```

Per-case:

- `fin_deep_ai_infra_nvda_dell_capex_023`: P30 root-cause audit pass; memo payload includes NVDA gross margin, DELL AI-optimized servers revenue, AMZN/GOOGL/MSFT capex, and DELL capex without the previous numeric display defects.
- `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025`: P30 root-cause audit pass; LRCX facts are no longer contradicted as missing, and MemoLogicPlan trace validation no longer fails.

Manual quality inspection still blocks broad 20-50:

- The AI infra output is materially better than R3/R5 but still too generic in dimension prose; it should make a sharper bounded judgment on DELL AI server quality, NVDA read-through, and cloud capex transmission.
- The semicap output still needs a stronger semicap playbook spine: bookings/backlog, EUV/DUV/tool mix, China/export exposure, customer concentration, and cycle position should dominate the memo, not generic capex/context rows.
- Automated eval still passes these two outputs even with weak analyst style; the next repair should harden thesis-led output-quality eval, not only absence-of-error gates.

## R7 Thesis-Led Required-Item Answer Plan

R7 addresses the next owned root cause from R6: the writer had enough facts to avoid numeric/source defects, but the MemoLogicPlan did not force each material question into a present bounded judgment. This produced conservative prose such as "needs further verification" instead of an analyst-style answer.

Implementation:

- `src/sec_agent/memo_logic_plan.py`
  - Adds `required_item_answer_plan` to MemoLogicPlan.
  - Adds per-required-item answer contracts for AI infra and semicap questions.
  - Propagates `required_item_answer_moves` into `writer_thesis_skeleton`.
  - Validates that every required question item has an answer plan and answer-first prompt.
- `src/sec_agent/memo_llm.py`
  - Compacts `required_item_answer_plan`, `answer_contract`, and section-level required item ids into the writer payload.
  - Updates the Memo Writer prompt to execute answer plans item by item: bounded judgment, evidence bridge, counter-read, and what-would-change-view.
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - Adds P30 root-cause rows when required items lack an answer plan.
  - Upgrades required-item rendered coverage so keyword-only or boundary-only text fails even if the exact term appears.
- `scripts/eval_multi_agent/audit_multi_agent_output_quality.py`
  - Adds `memo_surface_boundary_heavy_or_noncommittal`.
  - Adds boundary-language stats and maps this symptom to MemoLogicPlan/writer execution, not public-source absence.

Deterministic verification:

```text
python -m py_compile src/sec_agent/memo_logic_plan.py src/sec_agent/memo_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py scripts/eval_multi_agent/audit_multi_agent_output_quality.py
python -m pytest tests/test_memo_logic_plan.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_output_quality_audit.py -q
70 passed
```

Boundary:

- R7 deterministic repair is complete.
- R7 has not yet rerun the two DeepSeek full-chain cases. Broad 20-50 remains blocked until the AI/Semis cases prove the new answer-plan contract improves memo judgment density rather than only passing stricter tests.

## R8-R13 Economic-Role / Public Proxy / FPI Route Repair

After R7, the next two-case rerun exposed two more owned defects and one provider blocker.

Root causes found:

- Public proxy rows without a source/economic role were still too easy for selector/salvage logic to render as product revenue, order, backlog, or demand support.
- P30 economic-role misuse detection used broad windows; a sentence that correctly said DELL capex is not direct customer demand could be flagged because nearby text also discussed customer demand.
- ASML/FPI route coverage treated `6-K` as unavailable when the requested scope named `10-Q` or `8-K`, creating a false source gap even though the interim FPI filing route existed.

Implementation:

- `src/sec_agent/memo_llm.py`
  - Adds public-proxy-without-role detection.
  - Demotes such rows in supported-claim selection/context priority.
  - Rewrites salvage text so it says the row is only a product/official/external proxy lead and cannot be promoted to revenue, order, backlog, or customer-demand evidence.
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - Splits economic-role audit windows by sentence/line/chunk before matching.
  - Allows explicit negation/boundary language such as "not direct customer demand" or "cannot treat capex as supplier revenue" while still failing real capex-to-demand misuse.
- `src/sec_agent/mcp_tool_registry.py`
  - Adds SEC/FPI form equivalence: `20-F/40-F` for annual scope and `6-K` for interim/event scope.
  - Routes `6-K` through `8k_commentary`.
  - Stabilizes `source_coverage_gaps=[]` when no gaps exist so downstream contracts can reliably inspect the field.

Deterministic verification:

```text
python -m pytest tests/test_multi_agent_memo_llm_repair.py::test_salvage_public_proxy_without_role_is_not_rendered_as_product_revenue tests/test_multi_agent_memo_llm_repair.py::test_memo_supported_claim_selection_demotes_unroled_public_proxy_below_exact_role_fact tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_flags_economic_role_misuse tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_investment_quality_allows_role_boundary_opening -q
4 passed

python -m pytest tests/test_sec_agent_mcp_runtime_tools.py::test_mcp_registry_uses_fpi_6k_as_interim_route_without_false_sec_gap tests/test_sec_agent_mcp_runtime_tools.py::test_mcp_registry_returns_source_gap_when_manifest_scope_has_no_available_filings tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_flags_economic_role_misuse tests/test_multi_agent_real_llm_chain_eval.py::test_p30_root_cause_quality_allows_capex_customer_demand_boundary_language -q
4 passed

python -m pytest tests/test_d_series_fact_selection.py tests/test_memo_logic_plan.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_sec_agent_10q_source_contract.py -q
188 passed

python -m py_compile src/sec_agent/memo_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py src/sec_agent/d_series_fact_selection.py src/sec_agent/memo_logic_plan.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/mcp_tool_registry.py
```

R13 full-chain run:

```text
gate_status=fail
diagnostic_only=true
case_count=2
passed=0
failed=2
```

Interpretation:

- `fin_deep_ai_infra_nvda_dell_capex_023`: initial failure was `p30_root_cause_quality.economic_role_no_misuse`; artifact inspection showed this was an audit false positive caused by correct boundary language. After the R13 audit fix, the same rendered memo rescored with no economic-role misuse rows and investment-quality checks pass.
- `fin_deep_semicap_asml_amat_lrcx_klac_cycle_025`: run is not a valid product-quality judgment because DeepSeek returned `HTTP 402 Insufficient Balance` during specialist calls. The FPI/6-K route false source-gap issue is fixed deterministically, but the semicap full-chain closeout must be rerun with provider balance restored.

Boundary:

- R8-R13 fixed more upstream artifacts; it did not close broad full-chain readiness.
- Broad 20-50 remains blocked until a provider-healthy AI/Semis two-case rerun passes, the rendered memo is manually inspected, and Workbench can surface the run artifacts naturally.

## R14 Token Budget / Specialist Fanout / Prompt Payload Repair

R14 responds to the post-R13 cost review. The immediate goal was to stop spending paid LLM tokens on defects that can be isolated by deterministic or node-level tests.

Root causes fixed:

- Full-chain eval had no mandatory preflight budget plan and could enter paid model calls before discovering run/case/provider cost issues.
- Deep AI/Semis cases could activate too many specialists because the activation policy trusted broad deep-research scope more than the case's required items.
- Specialist prompts received large upstream packs repeatedly; pack compaction existed for some repair paths but not for the primary specialist request payload.
- Output-quality audit recorded token inefficiency, but the full-chain aggregate did not fail hard on low rendered-claim efficiency / high token cost patterns.

Implementation:

- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - Adds `--token-budget-preflight-only`, `--token-budget-total`, `--token-budget-per-case`, `--max-paid-calls`, `--allow-expensive-llm`, and `--token-budget-plan-path`.
  - Writes a `token_budget_plan.json` before graph/model construction.
  - Blocks paid runs before model calls when estimated run tokens, per-case tokens, or paid-call count exceed budget.
  - Adds aggregate token-budget summary and a blocking output-cost quality gate for high token cost, low claim efficiency, memo payload density failure, specialist low-yield, and all-specialists-active patterns.
- `src/sec_agent/multi_agent_runtime.py`
  - Adds the default-on `SEC_AGENT_SPECIALIST_REQUIRED_ITEM_GATE`.
  - Specialist activation now records matched required-item counts and skips low/supporting/conditional specialists without required-item match, explicit user intent, or visible core evidence.
- `src/sec_agent/specialist_llm.py`
  - Replaces raw prompt-passed product/capital/fundamental/peer packs with role-specific compact wrappers.
  - Adds prompt pack caps for ProductSpecPack, CapitalMacroPack, FundamentalStatementPack, and FundamentalPeerStatementPanel.
  - Truncates long text fields before the specialist prompt instead of relying on downstream writer/verifier gates.
- `tests/test_multi_agent_real_llm_chain_eval.py`
  - Adds no-paid token-budget preflight tests proving the CLI can write a plan and block before graph/model calls.
- `tests/test_multi_agent_specialist_llm.py`
  - Adds prompt-pack compaction regression for large product and peer rows.

No paid LLM was called in this repair.

Verification:

```text
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_output_quality_audit.py -q
122 passed

python -m pytest tests/test_multi_agent_contracts.py tests/test_memo_logic_plan.py tests/test_multi_agent_memo_llm_repair.py -q
93 passed

python -m compileall -q src/sec_agent/specialist_llm.py src/sec_agent/multi_agent_runtime.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
```

Two-case AI/Semis preflight:

```text
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --case-catalog-path tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json --case-id fin_deep_ai_infra_nvda_dell_capex_023 --case-id fin_deep_semicap_asml_amat_lrcx_klac_cycle_025 --output-dir eval/sec_cases/outputs/p30_token_budget_preflight --run-id 20260702_p30_token_budget_preflight_ai_semis_r1 --token-budget-preflight-only
```

Result:

```text
status=blocked_preflight_token_budget
allowed=false
estimated_total_tokens=272000
estimated_paid_call_count=18
token_budget_total=180000
token_budget_per_case=120000
max_paid_calls=8
```

Boundary:

- R14 prevents the next accidental high-cost full-chain run.
- R14 does not prove the final memo is now better; it proves the runtime will not pay for another broad run until node-level budget and activation constraints are satisfied.
- Next paid full-chain requires either lower estimated budget after more deterministic pruning or explicit override with `--allow-expensive-llm`.
