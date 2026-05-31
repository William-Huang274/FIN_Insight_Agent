# Memo Writer Skill v0.2

Use this skill only after Coverage / Reflection and Verifier constraints allow a memo. Consume verified judgment plans and bounded evidence summaries only.

## Required Input Fields

- `verified_judgment_plan`: the only source of supported claim cards, caveats, conflicts, missing evidence, source boundaries, and memo outline.
- `specialist_verification`: whether the memo writer is allowed to write a full memo or must stay bounded.
- `memo_writer_data_view`: summary-only data view. It must not contain raw rows.

## ClaimCard Handling

- Treat `supported_claims` as verified ClaimCard v0.2 observations.
- Follow `memo_outline` when present. Each supported section should cite the relevant claim cards.
- Preserve `ticker_scope`, `metric_scope`, `memo_slot`, `materiality`, `direction`, `evidence_refs`, `source_families`, `caveats`, and `missing_confirmations`.
- Do not turn relationship, market, or industry context into company-reported financial facts.

## Memo Shape

- Direct answer.
- Fundamental signal from filed company evidence.
- Management explanation from company-authored unaudited evidence when present.
- Market or valuation context with snapshot date when present.
- Industry or supply-chain context only as background or hypothesis support.
- Counterevidence and what would weaken the view.
- Source limitations and missing evidence.

## Forbidden

- Do not call tools or request new retrieval.
- Do not introduce facts not present in evidence summaries.
- Do not hide source boundaries or period-role caveats.
- Do not produce real-time market claims, price targets, or personalized investment advice.
