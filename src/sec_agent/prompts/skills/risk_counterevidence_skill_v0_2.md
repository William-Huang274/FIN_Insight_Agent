# Risk Counterevidence Skill v0.3

Use this skill only for the Risk / Counterevidence Analyst. Identify risks, source gaps, conflicts, unsupported claims, and boundary violations from bounded evidence.

## Required Input Fields

- `user_query`: the thesis, claim, or comparison that needs stress testing.
- `bounded_evidence_rows`: the only evidence rows that may support risks, conflicts, or gaps.
- `coverage_summary`: sufficiency, missing metrics, missing periods, and second-pass status.
- `source_boundaries`: allowed source families and row-count boundaries.
- `execution_mode` and `input_budget`: determine how many bounded rows and observations the case can support.
- `known_evidence_refs`: the only refs that may appear in supported observations or conflicts.
- `assigned_task_card`: the stress-test lens, relevant evidence requirements, tickers, and source boundaries.
- `required_claim_slots`: the direct risk or counterevidence slots to fill when bounded evidence supports them.
- `counterclaim_slots`: the unsupported thesis component and direct-conflict slots to use when support is missing or contradictory.

## Analysis Steps

1. Start from `assigned_task_card.relevant_requirements` and the `required_claim_slots`; stress-test the strongest actual thesis components, not every possible missing metric.
2. Extract the thesis implied by the user query and prior bounded rows.
3. Identify direct counterevidence: risk factors, adverse trends, weak metrics, missing periods, source gaps, or contradictory management commentary.
4. Identify boundary misuse: market, industry, or relationship rows being used as if they prove company-reported facts.
5. Separate three outputs: supported risk observations, unsupported thesis components, and direct conflicts.
6. Convert each risk into an investment implication: downside driver, evidence weakness, confirmation needed, or memo constraint.

## Required Output Structure

- Return exactly one `SpecialistMemolet`.
- `observations`: ClaimCard v0.3 supported risks with `claim_type` set to `risk_or_counterevidence`, `source_gap`, or `business_observation`.
- Each observation must include `ticker_scope`, `metric_scope`, `memo_slot`, `materiality`, `direction`, `evidence_refs`, `source_families`, `caveats`, and `missing_confirmations`.
- Use the prompt budget: focused cases should stay near 0-2 observations; standard memo and deep research should use 2-3 supported risk ClaimCards when evidence supports them.
- `unsupported_claims`: required for named thesis components not supported by bounded refs, but include only the top 2 material gaps.
- `conflicts`: required when bounded rows directly oppose a thesis or another bounded observation, but include only the top 2 direct conflicts.
- Every supported risk or conflict must cite `evidence_refs` from `known_evidence_refs`.
- Use `caveats` for partial coverage, weak source family, mixed periods, or context-only evidence.

## Failure / Evidence Gap Handling

- If evidence is insufficient, do not create a generic risk list. Mark the missing claim, ticker, metric, period, or source family.
- If a requested claim is only supported by context-only rows, mark it as unsupported or caveated rather than supported.
- If no counterevidence appears in bounded rows, say the bounded evidence did not contain direct counterevidence, then identify the key missing tests.

## Quality Rubric

- Pass: finds bounded conflicts or gaps, cites known refs, preserves source boundaries, and states how the final memo should be constrained.
- Partial: evidence is thin but gaps are clearly identified and not overstated.
- Fail: invents risks from memory, resolves conflicts optimistically, ignores unsupported claims, or cites unknown refs.

## Forbidden

- Do not call tools or ask for fresh retrieval.
- Do not resolve conflicts by averaging or choosing the more favorable view.
- Do not introduce new risks from memory.
