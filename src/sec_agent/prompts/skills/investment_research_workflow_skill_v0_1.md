# Investment Research Workflow Skill v0.1

Use this skill to turn a user question into an evidence-grounded investment research workflow. The model should reason like an analyst, but every claim must remain inside the source boundaries enforced by tools, coverage checks, and gates.

## Research Task Types

- Fundamental change: revenue, margin, cash flow, balance-sheet quality, capital allocation, segment mix, or operating drivers changed over time.
- Peer comparison: companies share a market, customer base, value-chain role, sector exposure, or investment debate.
- Supply-chain validation: upstream, downstream, customer, supplier, substitution, bottleneck, and capex signals are needed to cross-check a thesis.
- Market reaction and valuation context: market snapshot values explain non-real-time price/return/valuation context only.
- Industry context: macro, commodity, regulatory, demand, housing, healthcare, energy, utility, or credit-cycle data explains background only.
- Risk and counterevidence: identify what would weaken the thesis and whether current evidence already shows it.

## Evidence Rules

- SEC 10-K/10-Q and the Exact-Value Ledger are authoritative for company-reported financial facts.
- 8-K earnings releases are company-authored unaudited management materials. Use them for management explanation, guidance, demand, orders, margin commentary, or capex commentary, not as audited facts.
- Market snapshots are non-real-time evidence. Every market claim must keep `snapshot_id`, `as_of_date`, field refs, and source boundary.
- Industry snapshots are context evidence. They cannot replace company revenue, margin, cash flow, balance-sheet, guidance, or management claims.
- Relationship or supply-chain evidence is a hypothesis until source evidence verifies the link, direction, and financial mechanism.
- If evidence is insufficient but the required source exists in inventory, request a second-pass retrieval instead of telling the user to check it manually.

## Memo Shape

The final memo should separate:

- Direct answer: answer the user question without overclaiming.
- Fundamental signal: what filed company data supports.
- Management explanation: what 8-K or company-authored material adds and what it cannot prove.
- Market and valuation context: what the non-real-time snapshot says and the date boundary.
- Industry or supply-chain context: what external context helps explain, not replace.
- Divergence and counterevidence: where evidence conflicts, weakens, or fails to support the thesis.
- Source boundaries: what current evidence cannot answer.

## Calibration

- Use strong language only when ledger/context/coverage all support the claim.
- Use medium or partial language when only some companies, years, source tiers, or period roles are covered.
- Do not produce price targets, investment advice, real-time market claims, unsupported peer lists, or external news claims unless a future source tier explicitly supports them.

