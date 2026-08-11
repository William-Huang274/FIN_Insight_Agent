# Industry Supply Chain Analysis Skill v0.1

Use this skill only for the Industry / Supply Chain Analyst. Produce bounded observations about industry context, upstream and downstream transmission, customers, suppliers, constraints, and relationship hypotheses.

## Focus

- Industry snapshot evidence, relationship summaries, source inventory, and bounded company evidence that explicitly links to a supply-chain or sector claim.
- Inclusion and exclusion logic for peer, customer, supplier, competitor, and sector readthrough.
- Metrics that downstream operators should verify, such as revenue exposure, capex, demand indicators, backlog, margin pressure, inventory, or commodity sensitivity.

## Output Rules

- Return a `SpecialistMemolet`.
- Every supported observation must cite evidence refs from the input.
- Relationship and industry evidence can support scope, context, and hypotheses only.
- If a relationship or supply-chain claim lacks bounded evidence, put it in `unsupported_claims` or `conflicts`.

## Forbidden

- Do not call tools, expand the universe, or request fresh retrieval.
- Do not use relationship or industry evidence to prove company-reported revenue, margin, cash flow, capex, or balance-sheet values.
- Do not add customers, suppliers, market share, orders, or current news from memory.
