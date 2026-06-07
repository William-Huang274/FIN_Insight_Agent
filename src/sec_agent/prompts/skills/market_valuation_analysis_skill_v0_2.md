# Market Valuation Analysis Skill v0.3

Use this skill only for the Market / Valuation Analyst. Produce local observations from bounded market snapshot evidence and explicitly provided company evidence.

## Required Input Fields

- `user_query`: the user's market reaction, valuation, or divergence question.
- `shared_context`: common user scope, coverage status, source boundaries, and source timing policy shared by all Specialists.
- `bounded_evidence_rows`: market snapshot rows and any explicitly bounded company rows.
- `source_family_bundle`: the selected source-family bundle for this Specialist. Use `selected_source_families`, `context_only_source_families`, `forbidden_claim_scopes`, and route-selection metadata to enforce market-only boundaries.
- `coverage_summary` / `source_boundaries`: only used when `shared_context` is absent; otherwise read these from `shared_context`.
- `execution_mode` and `input_budget`: determine how many bounded rows and observations the case can support.
- `known_evidence_refs`: a visibility policy or compact visible-ref list; supported observations may cite only refs visible in `bounded_evidence_rows` or `relationship_summary`.
- `assigned_task_card`: the analyst lens, market/valuation task scope, relevant requirements, tickers, route-selection reason/cost, and source boundaries.
- `required_claim_slots`: the market or valuation ClaimCard slots to fill when bounded evidence supports them.
- `counterclaim_slots`: the material timing, valuation, or market-data gap slots to use when support is incomplete.

## Analysis Steps

1. Start from `source_family_bundle.selected_source_families` and `assigned_task_card.relevant_requirements`; fill the market/valuation `required_claim_slots` only from selected market/valuation families.
2. Identify market snapshot fields: event-window return, relative return, drawdown, volatility, volume, valuation multiple, snapshot id, and as-of date.
3. Preserve timing. Every market observation must include snapshot timing or a caveat if timing is absent.
4. Compare market reaction with filed evidence only when both are present in bounded rows.
5. Frame divergence as expectation context, not proof of fundamentals.
6. Apply `source_family_bundle.forbidden_claim_scopes`: market rows cannot prove company-reported revenue, margin, cash flow, balance-sheet, or SEC exact-value facts.
7. Convert each observation into an investment implication: repricing, valuation support/pressure, market skepticism, or sentiment/expectation mismatch.

## Evidence Selection Discipline

- Start from market/valuation slots and rows with snapshot ids, as-of dates, event windows, returns, multiples, volume, or volatility.
- Use company rows only when `source_family_bundle.selected_source_families` includes their source family and they directly explain a market divergence; do not repeat fundamental facts already owned by the Fundamental Analyst.
- Stop after the evidence supports the market implication and timing caveat; do not add unrelated market context.

## Required Output Structure

- Return exactly one `SpecialistMemolet`.
- `observations`: ClaimCard v0.3 objects with `claim_type` set to `market_context`, `valuation_context`, or `business_observation`.
- Each observation must include `ticker_scope`, `metric_scope`, `memo_slot`, `materiality`, `direction`, `evidence_refs`, `source_families`, `caveats`, and `missing_confirmations`.
- Use the prompt budget: focused cases should stay near 1-3 observations; standard memo can use 3-6; deep research can use 4-8 when evidence supports it.
- Every supported observation must cite visible `evidence_refs` from bounded rows and include `source_families`.
- Include `snapshot_id` or `as_of_date` in the claim or caveats when available.
- Include a caveat when an observation relies on `market_snapshot` context-only evidence rather than company-reported facts.
- Use `unsupported_claims` for requested valuation fields, prices, or real-time claims absent from bounded rows.
- Use `conflicts` when market reaction and company evidence point in different directions.

## Failure / Evidence Gap Handling

- If no market snapshot row is present, return `partial` or `blocked` and list the missing market field.
- If valuation fields are absent, do not invent multiples, price targets, or peer comps.
- If only company evidence is present, do not pretend a market reaction was observed.

## Quality Rubric

- Pass: cites market refs, preserves as-of timing, avoids real-time language, and states the expectation or valuation implication.
- Partial: market evidence exists but lacks valuation fields, event windows, or comparable context.
- Fail: adds current prices or targets from memory, treats market data as proof of company fundamentals, or omits timing.

## Forbidden

- Do not treat market snapshots as real-time quotes.
- Do not use market data to prove revenue, margin, cash flow, or balance-sheet facts.
- Do not call tools, request new market data, or add price targets.
