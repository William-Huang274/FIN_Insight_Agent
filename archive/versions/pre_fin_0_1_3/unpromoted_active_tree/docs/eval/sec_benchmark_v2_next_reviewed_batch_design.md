# SEC Benchmark v2 Next Reviewed Batch Design

Date: 2026-05-19

This is a design artifact for the next v2 reviewed batch after
`test_cases_v2_pilot_plus3_seed.jsonl`. It is not yet a runnable benchmark
manifest. The current accepted v2 state is plus3: 9 total cases, 8 non-trap
reviewed cases, and 1 trap case, with BGE-M3 pipeline-context, Judgment Plan,
Qwen9B, and post-gates passing including metric-source grounding.

Implementation status update:

- `AMZN_AWS_NUMERIC_2023_2025_001` has been promoted into
  `test_cases_v2_pilot_plus4_seed.jsonl`, passed deterministic reviewed-gold
  gates, and then passed BGE-M3 + Judgment Plan + RTX 5090 Qwen9B post-gates.
- `AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001` has been promoted
  into `test_cases_v2_pilot_plus5_seed.jsonl` as a strict AMZN/GOOGL split from
  the broad cloud-profitability artifact, excluding Microsoft proxy rows. It
  passed deterministic reviewed gates and final BGE-M3 + Judgment Plan + RTX
  5090 Qwen9B post-gates.
- `MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001` has been promoted into
  `test_cases_v2_pilot_plus6_seed.jsonl` as a strict MSFT split from the broad
  cloud-profitability artifact. It passed deterministic reviewed gates and final
  BGE-M3 + Judgment Plan + RTX 5090 Qwen9B post-gates while preserving the rule
  that Microsoft Cloud revenue and gross margin are proxy evidence, not exact
  Azure metrics.
- `MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001` has been promoted into
  `test_cases_v2_pilot_plus7_seed.jsonl` as a pipeline-only metric-scope
  not-found trap. It passed deterministic trap gates, activated the
  `required_not_found_missing` semantic check, and passed final BGE-M3 +
  Judgment Plan + RTX 5090 Qwen9B post-gates.
- `NVDA_DATACENTER_2023_2025_001` and `SNOW_RISK_2023_2025_001` have been
  promoted into `test_cases_v2_pilot_plus8_seed.jsonl` as reviewed text-heavy
  no-ledger cases. They passed deterministic reviewed gates and final BGE-M3 +
  Judgment Plan + RTX 5090 Qwen9B post-gates, including abstract judgment,
  caveat/claim, named-fact, v2 semantic, and no-ledger consistency checks.
- The plus8 MVP freeze-readiness review is complete:
  `reports/quality/sec_benchmark_v2_pilot_plus8_mvp_freeze_readiness_review.json`.
  Decision: plus8 can be frozen as an MVP diagnostic pack, but it cannot be
  claimed as the full v2 benchmark or used for full mainline scored testing.
- The continuation alias for this state is `v2_plus8_mvp_diagnostic_freeze`;
  see `docs/worklog/107_handoff_v2_plus8_mvp_freeze_next.md`.
- Post-freeze branch decision: harden the frozen plus8 validation surface before
  plus9 or full-v2 expansion; see
  `docs/worklog/108_sec_benchmark_v2_post_freeze_branch_decision.md`.
- First hardening step completed: expanded abstract-judgment rubric coverage now
  checks all 13 non-trap plus8 cases and passes at
  `reports/quality/sec_benchmark_v2_pilot_plus8_abstract_judgment_gate_expanded.json`.
- Second hardening step completed: reviewed gold-context Qwen output and active
  gold-vs-pipeline parity now pass at
  `reports/quality/local_v2_pilot_plus8_gold_vs_pipeline_parity_post_gates/sec_benchmark_post_gates_summary.json`.

## Decision

Design the next batch as an MVP-extension batch, not a full v2 benchmark. The
target is to add 6 candidate cases:

- 4 non-trap reviewed cases that reuse or split existing reviewed context/facts.
- 1 text-heavy risk case with no exact-value ledger rows.
- 1 source-policy/not-found trap.

This would take v2 from 9 total cases to about 15 total cases before deciding
whether an MVP frozen pack is credible.

## Governance

- Hypothesis: plus3 already covers many numeric/table and peer-comparison
  mechanics; the next useful evidence is whether the system holds under cloud
  profitability comparability, Microsoft proxy disclosure, text-heavy risk
  calibration, and not-found/source-policy traps.
- Decision target: each promoted case must pass readiness, reviewed context/fact
  gates, ledger-unit gates where numeric rows exist, BGE-M3 pipeline-context
  trace, Judgment Plan validation, true-Qwen run, and active post-gates including
  metric-source grounding.
- Ceiling: this batch is diagnostic for MVP readiness. It is not the 40-case
  full v2 generalization target.
- Baseline: v2 plus3 metric-source grounded run passes all active post-gates
  with `qwen_answer_ratio=1.0`.
- Stop condition: do not promote a case if source availability cannot support
  the declared objective, if exact facts need unreviewed seed rows, or if the
  required validator does not exist.
- Decision label: proceed as design-only, then build reviewed artifacts case by
  case.

## Candidate Batch

| Priority | Candidate | Type | Why It Matters | Existing Evidence | Gate Focus |
|---:|---|---|---|---|---|
| 1 | `AMZN_AWS_NUMERIC_2023_2025_001` | L3 single-company numeric trend | Adds a clean AWS revenue plus operating-income trend case outside current v2 companies. | Reviewed facts already exist: 6 AWS revenue / operating-income rows; reviewed context has 11 rows. | metric role, ledger exactness, source grounding, prose trend direction |
| 2 | `AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001` | L4 two-company peer comparison | Tests comparable cloud segment revenue and operating income without Microsoft disclosure asymmetry. | Split 12 AMZN/GOOGL rows from `CLOUD_PROFITABILITY_2023_2025_DIAG_001`; context/facts exist but need new reviewed case packaging. | peer entity separation, comparable metrics, answer-vs-plan, metric-source grounding |
| 3 | `MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001` | L3 proxy/not-direct numeric+text | Tests Microsoft Cloud and Azure disclosure boundaries: Microsoft Cloud revenue/gross margin are broad proxy metrics, not Azure segment operating income. | MSFT reviewed context exists; Microsoft Cloud revenue proxy and gross margin rows exist inside `CLOUD_PROFITABILITY_2023_2025_DIAG_001`. | proxy-as-direct, non-comparable metric, caveat/claim, source policy |
| 4 | `NVDA_DATACENTER_2023_2025_001` | L3 text-heavy risk / driver summary | Adds year-specific AI/data-center driver and risk calibration without forcing invented product revenue. | Reviewed text context exists with 12 rows; no exact-value ledger rows needed. | named-fact support, year separation, weak-evidence overclaim, unsupported product revenue |
| 5 | `SNOW_RISK_2023_2025_001` | L3 text-heavy risk / not-found | Complements the plus3 Snowflake numeric case by testing consumption-model risk language and not-found discipline. | Reviewed text context exists with 9 rows; no exact-value ledger rows needed. | repeated-risk language, not-found, no customer-count invention |
| 6 | `MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001` | trap / source-policy not-found | Adds a metric-scope trap: exact Azure gross margin is not the same as Microsoft Cloud gross margin. | MSFT reviewed context can seed retrieval; no reviewed facts should be required for the trap answer. | source-policy violation, proxy-as-direct, unsupported exact metric, refusal quality |

## Case Notes

### `AMZN_AWS_NUMERIC_2023_2025_001`

Recommended action: promote first.

Rationale:

- It has the cleanest existing reviewed numeric artifact.
- It expands company/topic coverage without adding a new validator requirement.
- It gives a useful sanity check for trend prose and metric-source grounding on
  a non-v2-origin case migrated into v2.

Required v2 additions:

- Add `required_caveats` saying AWS revenue is not consolidated Amazon revenue.
- Add `disallowed_claims` blocking market-share and external-cloud-demand claims.
- Confirm the existing 6 reviewed facts enter the v2 ledger with distinct
  `cloud_revenue` and `operating_income` metric IDs.

### `AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001`

Recommended action: build after the AMZN single-company case.

Rationale:

- The previous broad `CLOUD_PROFITABILITY_2023_2025_DIAG_001` is too wide for
  the next v2 step because Microsoft is not directly comparable.
- AMZN and GOOGL both have cloud revenue and cloud operating income rows across
  2023-2025, so the peer comparison can be cleanly gated.

Required v2 additions:

- New reviewed context/facts should be a strict AMZN/GOOGL subset, not a copy of
  the broad 3-company cloud case.
- Required caveat: operating income comparison is segment-scope only and does
  not prove product-level margin or market share.
- Disallowed claims: no simple "cloud winner" unless tied to the exact metrics
  and caveats; no external market share or customer-growth claims.

### `MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001`

Recommended action: build third, after the comparable AMZN/GOOGL case.

Rationale:

- It isolates the Microsoft asymmetry instead of contaminating a peer case.
- It tests exactly the kind of proxy/direct boundary that matters for MVP
  credibility: Microsoft Cloud is a broad commercial cloud metric; Azure and
  exact Azure gross margin should not be fabricated.

Required v2 additions:

- Split Microsoft Cloud revenue proxy and Microsoft Cloud gross margin
  percentage rows from the existing broad cloud profitability reviewed facts.
- Required caveat: Microsoft Cloud includes Azure and other commercial cloud
  properties; it is not exact Azure revenue.
- Required caveat: Microsoft Cloud gross margin percentage is not cloud segment
  operating income and should not be compared one-for-one with AWS/Google Cloud
  operating income.

### `NVDA_DATACENTER_2023_2025_001`

Recommended action: include as text-heavy generalization.

Rationale:

- Current v2 is still heavy on ledger-backed numeric cases. MVP needs at least
  one difficult text-only risk/driver case that cannot be solved by table cells.
- This case tests year-specific disclosure organization and named-fact support.

Required v2 additions:

- Add `required_caveats` for export controls, supply/customer concentration, or
  demand uncertainty when supported by cited text.
- Add `disallowed_claims` blocking exact GPU product revenue, stock price,
  external news, or market-share claims.
- Keep `numeric_checks=[]`; any precise product/AI GPU revenue should be
  treated as unsupported unless directly reviewed into a ledger later.

### `SNOW_RISK_2023_2025_001`

Recommended action: include as text-heavy not-found/risk counterpart to plus3.

Rationale:

- Plus3 proved numeric separation for Product revenue, NRR, RPO, and RPO
  recognition timing. This case tests whether the model can discuss
  consumption-model risk without inventing customer counts or retention claims.

Required v2 additions:

- Add `required_caveats` for consumption variability, forecasting difficulty,
  or revenue timing if cited.
- Add `disallowed_claims` blocking customer counts, retention trend claims, and
  non-SEC market commentary unless cited.
- Keep `numeric_checks=[]` unless a future reviewed fact explicitly requires a
  number.

### `MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001`

Recommended action: add as the next trap/source-policy case.

Rationale:

- Current v2 has one wrong-attribution trap. It does not yet strongly test
  metric-scope not-found behavior.
- This trap is realistic: the filing can discuss Microsoft Cloud gross margin,
  Azure growth, and AI infrastructure pressure, but the model must not output
  an exact Azure gross margin.

Required v2 additions:

- `evaluation_modes=["pipeline_context"]`.
- `task_type="anti_hallucination_metric_scope_not_found"`.
- Required refusal: state that exact Azure gross margin is not disclosed in the
  provided SEC evidence.
- Allowed caveat: may mention Microsoft Cloud gross margin only as a broad proxy
  if retrieved evidence supports it.
- Disallowed claim: any exact "Azure gross margin" value or treating Microsoft
  Cloud gross margin as Azure gross margin.

## Deferred Candidates

- `AAPL_SERVICES_MARGIN_2023_2025_001`: defer because current v2 already has a
  stronger Apple product/services revenue and gross-margin table case.
- `GOOGL_CLOUD_CONTEXT_ROLE_2025_001`: defer as a narrow single-year regression;
  its value is better absorbed into the AMZN/GOOGL peer cloud case.
- `CLOUD_PROFITABILITY_2023_2025_DIAG_001`: do not promote as-is. Split it into
  the two cloud cases above to avoid three-company comparability ambiguity.
- `SNOW_PRODUCT_GROSS_MARGIN_TRAP_001`: defer until source precheck confirms the
  disclosure is actually absent. If Snowflake discloses product gross profit or
  product gross margin, this is not a valid trap.

## Build Order

1. Promote `AMZN_AWS_NUMERIC_2023_2025_001` with v2 caveats and disallowed
   claims. Completed in plus4.
2. Build `AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001` from the
   reviewed cloud profitability AMZN/GOOGL subset. Completed in plus5.
3. Build `MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001` from the Microsoft subset.
   Completed in plus6.
4. Add the text-heavy `NVDA_DATACENTER_2023_2025_001` and
   `SNOW_RISK_2023_2025_001` with v2 caveat/claim fields. Completed in plus8.
5. Add `MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001` as the new trap.
   Completed in plus7 before the text-heavy cases because it directly closed
   the Microsoft Cloud proxy disclosure-boundary path from plus6.
6. Run readiness and gold gates before any pipeline-context Qwen run.

## Acceptance For This Batch

This batch has now met the MVP frozen-pack diagnostic acceptance criteria:

- Reviewed-gold gates passed for all 13 non-trap cases.
- Trap smoke passed for both pipeline-only traps.
- Exact-value ledger and ledger-unit gates passed for 104 rows.
- BGE-M3 remains the only final selector; BM25/ObjectBM25 stay candidate
  generators.
- Full post-gates passed with `qwen_answer_ratio=1.0`, no non-trap fallback, no
  ledger repair, and `metric_source_grounding_gate_pass=true`.

Freeze boundary:

- The plus8 pack is acceptable as an MVP diagnostic freeze.
- It is still not the 40-case full v2 benchmark.
- Full mainline scored testing remains blocked by the partial-approval decision.
- The abstract-rubric coverage gap is closed for plus8 non-trap cases.
- Gold-vs-pipeline parity is now active and passing for 13 comparable non-trap
  cases.
- Post-freeze validation hardening is complete for the plus8 MVP diagnostic
  freeze. The next choice is plus9 coverage-matrix design versus a full-v2 route
  plan.
