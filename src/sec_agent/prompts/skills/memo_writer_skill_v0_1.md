# Memo Writer Skill v0.2

Use this skill only after Coverage / Reflection and Verifier constraints allow a memo. Consume verified judgment plans and bounded evidence summaries only.

## Required Input Fields

- `verified_judgment_plan`: the only source of supported claim cards, caveats, conflicts, missing evidence, source boundaries, and memo outline.
- `specialist_verification`: whether the memo writer is allowed to write a full memo or must stay bounded.
- `shared_memo_context`: common scope, coverage, Specialist route status, and source-boundary context. It must not be treated as evidence for a factual claim.
- `memo_writer_data_view`: deprecated summary-only data view. If present, it must not contain raw rows.

## ClaimCard Handling

- Treat `memo_thesis_pack` as the primary writing brief when present; use `memo_thesis_plan` to order the memo.
- Treat `supported_claims` as fallback verified ClaimCard observations only when a thesis pack is absent.
- If `memo_thesis_pack.status` or `memo_thesis_plan.status` is `ready`, return `answer_status=draft` with non-empty `memo_claims`. Use `blocked_by_judgment_plan` only when no verified memo-ready thesis or driver claim exists.
- Follow `memo_outline` when present. Each supported section should cite the relevant claim cards.
- Emit `memo_generation_policy=thesis_led_claim_cards_v0_1`. Emit only a compact `memo_thesis_plan` carrying status, primary thesis id, primary thesis, and direction; do not copy the full plan or thesis pack.
- Preserve `ticker_scope`, `metric_scope`, `memo_slot`, `materiality`, `direction`, `evidence_refs`, `source_families`, `caveats`, and `missing_confirmations`.
- Preserve numeric values exactly as written in ClaimCards. Do not recalculate, invent, round, or change units; if a sentence must be shortened, omit a number instead of altering it.
- Do not turn relationship, market, or industry context into company-reported financial facts.
- Do not summarize every ClaimCard. Select the core thesis, 2-4 strongest drivers, the strongest counterargument, and the most important source boundary.

## Memo Shape

- Direct answer with a bounded thesis.
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
