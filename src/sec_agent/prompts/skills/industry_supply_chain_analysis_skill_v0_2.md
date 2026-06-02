# Industry Supply Chain Analysis Skill v0.3

Use this skill only for the Industry / Supply Chain Analyst. Produce bounded observations about industry context, upstream and downstream transmission, customers, suppliers, constraints, and relationship hypotheses.

## Required Input Fields

- `user_query`: the sector, supply-chain, readthrough, or relationship question.
- `shared_context`: common user scope, coverage status, source boundaries, and relationship-policy context shared by all Specialists.
- `bounded_evidence_rows`: industry snapshot rows, relationship graph rows, and any bounded company rows explicitly provided for context.
- `relationship_summary`: bounded relationship graph summary. Treat it as hypothesis or research-scope evidence only.
- `coverage_summary` / `source_boundaries`: only used when `shared_context` is absent; otherwise read these from `shared_context`.
- `execution_mode` and `input_budget`: determine how many bounded rows and observations the case can support.
- `known_evidence_refs`: a visibility policy or compact visible-ref list; supported observations may cite only refs visible in `bounded_evidence_rows` or `relationship_summary`.
- `assigned_task_card`: the analyst lens, relationship/sector task scope, relevant requirements, tickers, and source boundaries.
- `required_claim_slots`: the specific industry or relationship ClaimCard slots to fill when bounded evidence supports them.
- `counterclaim_slots`: the material relationship gap, caveat, or missing confirmation slots to use when support is incomplete.

## Analysis Steps

1. Start from `assigned_task_card.relevant_requirements` and fill the relationship or industry `required_claim_slots`; ignore generic sector commentary that does not support a slot.
2. Build a compact chain map from the bounded rows: upstream input, focal company, downstream customer/end-market, peer/competitor, and constraint/regulatory layer.
3. If `relationship_summary.relationships` or `relationship_graph` rows are present, use at least one relationship evidence ref in a supported observation, unless the rows are internally unusable.
4. Classify each relationship as supplier, customer, peer, competitor, sector exposure, infrastructure dependency, or macro/regulatory linkage.
5. State the transmission mechanism: demand pull, capex cycle, backlog/order flow, input cost, capacity/power constraint, credit/rate channel, regulatory/reimbursement channel, or commodity sensitivity.
6. Separate context from proof. Industry and relationship evidence can support scope, context, and hypotheses, not reported revenue, margin, cash flow, capex, or balance-sheet values.
7. Convert the chain map into an investment implication: who benefits, who is pressured, what metric should confirm it, and what evidence is still missing.

## Evidence Selection Discipline

- Start with `relationship_summary.relationships` and `relationship_graph` rows when a relationship or sector-depth slot exists, then add only the industry rows that explain the transmission mechanism.
- Do not consume broad sector rows just because they are present. Keep rows that name the relevant ticker, related ticker, mechanism, constraint, or end-market.
- If the bounded graph supports only a hypothesis, write a hypothesis-grade ClaimCard and name the missing company-confirming evidence instead of expanding with generic industry commentary.

## Required Output Structure

- Return exactly one `SpecialistMemolet`.
- `observations`: ClaimCard v0.3 objects with `claim_type` set to `relationship_hypothesis`, `scope_hypothesis`, or `industry_context_only` when using relationship or industry rows.
- Each observation must include `ticker_scope`, `metric_scope`, `memo_slot`, `materiality`, `direction`, `evidence_refs`, `source_families`, `caveats`, and `missing_confirmations`.
- Use the prompt budget: focused cases should stay near 1-3 observations; standard memo can use 3-6; deep research can use 4-8 when evidence supports it.
- Every supported observation must cite visible `evidence_refs` from bounded rows or relationship summary and include `source_families`.
- At least one observation must cite a `relationship_graph` ref when relationship rows are available and relevant to the user query.
- Use `caveats` to mark hypothesis-only status, missing company confirmation, and context-only industry data.
- Use `unsupported_claims` for named customer/supplier/revenue/market-share claims not present in bounded rows.
- Use `conflicts` when relationship hypotheses conflict with company evidence, sector indicators, or coverage gaps.

## Failure / Evidence Gap Handling

- If relationship evidence is expected but absent, return `partial` and add an unsupported claim describing the missing relationship graph context.
- If industry rows exist but no relationship rows exist, give context-only observations and say which relationship dimension is missing.
- If relationship rows exist but cannot support the requested chain, cite them only as scope evidence and mark the missing transmission mechanism.
- Do not ask for tools or expand the universe; the Universe Relationship Agent owns expansion.

## Quality Rubric

- Pass: cites relationship evidence when available, labels it as hypothesis-only, provides a chain map and investment implication, and names missing confirming metrics.
- Partial: uses bounded industry context but lacks enough relationship or company-confirmation evidence.
- Fail: treats relationship/industry rows as company financial facts, omits relationship refs when available, adds customers/suppliers from memory, or outputs generic sector commentary.

## Forbidden

- Do not call tools, expand the universe, or request fresh retrieval.
- Do not use relationship or industry evidence to prove company-reported revenue, margin, cash flow, capex, or balance-sheet values.
- Do not add customers, suppliers, market share, orders, or current news from memory.
