# Memo Writer Skill v0.2

Use this skill only after Coverage / Reflection and Verifier constraints allow a memo. Consume verified judgment plans and bounded evidence summaries only.

## Required Input Fields

- `verified_judgment_plan`: the only source of supported claim cards, caveats, conflicts, missing evidence, source boundaries, and memo outline.
- `judgment_state`: compact dimension-level adjudication state inside `verified_judgment_plan`; use it before raw driver lists when present.
- `specialist_verification`: whether the memo writer is allowed to write a full memo or must stay bounded.
- `shared_memo_context`: common scope, coverage, Specialist route status, and source-boundary context. It must not be treated as evidence for a factual claim.
- `memo_writer_data_view`: deprecated summary-only data view. If present, it must not contain raw rows.

## ClaimCard Handling

- Treat `judgment_state.dimension_judgments` as the primary writing brief when present. Use `thesis_driver_pack.dimension_sections`, `memo_thesis_pack`, and `memo_thesis_plan` to order and bound the memo.
- Treat `supported_claims` as fallback verified ClaimCard observations only when a thesis pack is absent.
- If `memo_thesis_pack.status` or `memo_thesis_plan.status` is `ready`, return `answer_status=draft` with non-empty `memo_claims`. Use `blocked_by_judgment_plan` only when no verified memo-ready thesis or driver claim exists.
- Follow `memo_outline` when present. Each supported section should cite the relevant claim cards.
- Emit `memo_generation_policy=thesis_led_claim_cards_v0_1`. Emit only a compact `memo_thesis_plan` carrying status, primary thesis id, primary thesis, and direction; do not copy the full plan or thesis pack.
- Emit `dimension_analyses` when judgment-state dimensions or thesis-driver dimension sections are present. Each item needs `dimension_id`, `title`, `summary`, `business_mechanism`, `financial_bridge`, `competitive_read` or `counter_read`, `claim_ids`, and `evidence_refs`.
- Preserve `ticker_scope`, `metric_scope`, `memo_slot`, `materiality`, `direction`, `evidence_refs`, `source_families`, `caveats`, and `missing_confirmations`.
- Preserve numeric values exactly as written in ClaimCards. Do not recalculate, invent, round, or change units; if a sentence must be shortened, omit a number instead of altering it.
- Do not turn relationship, market, or industry context into company-reported financial facts.
- Do not summarize every ClaimCard or list drivers one by one. Organize the memo by analyst dimensions such as fundamentals, product/production, capital/financing, competition/market position, industry/supply chain, and risk/counterevidence.

## Memo Shape

- Direct answer with a dense bounded thesis across the strongest dimensions, not a row recap.
- Dimension-led analysis sections that connect evidence to business mechanism, financial bridge, competitive/risk context, and evidence boundary.
- 3-5 memo claims when the thesis pack is ready and enough ClaimCards exist, ordered by thesis plan, each carrying claim id and evidence refs.
- Fundamental signal from filed company evidence when supported.
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
