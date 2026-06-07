# Relationship Universe Skill v0.1

Use this skill only for Universe / Relationship planning. Expand research scope from bounded relationship evidence and source inventory.

## Focus

- Peer, competitor, customer, supplier, sector, and macro-sensitive relationship scope.
- Inclusion and exclusion rationale for focus tickers and expanded tickers.
- Evidence needs that downstream operators can compile.
- Professional universe construction from a bounded catalog: peers, competitors, upstream suppliers, downstream customers, infrastructure dependencies, power/utilities readthrough, non-US supply-chain disclosure companies, and sector or macro-sensitive proxies.
- Source coverage awareness: whether each candidate has SEC primary filings, company-authored unaudited material, market snapshot, industry snapshot, relationship graph rows, or global public disclosure coverage.

## Output Rules

- Return a `UniverseRelationshipPlan`.
- Relationship evidence can support scope and hypotheses only.
- Full-universe or sector-representative scope must include a short rationale.
- Missing relationship evidence must become an unsupported relationship, not a supported expansion.
- Each included non-focus ticker must have an inclusion rationale, candidate lens, source family needed, and whether the relationship is verified, inferred, hypothesis-only, or a source gap.
- Exclude plausible but unsupported companies when the catalog/source coverage cannot support them; record short exclusion rationale rather than expanding blindly.
- Keep the expanded ticker budget tight. Prefer a representative, evidence-seeking candidate set over all companies in a sector.
- When the current bounded relationship lookup is insufficient, emit evidence requirements or unsupported relationships for Coverage / Reflection; do not fill the gap from model memory.

## Forbidden

- Do not prove revenue, margin, cash flow, or balance-sheet facts from relationship graph evidence.
- Do not expand to all companies without relationship evidence and a budget guard.
- Do not choose physical graph paths, databases, or retrieval tools.
- Do not add customers, suppliers, or named counterparties only from general market knowledge.
