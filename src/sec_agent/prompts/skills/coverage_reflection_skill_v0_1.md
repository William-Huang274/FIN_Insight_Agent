# Coverage Reflection Skill v0.1

Use this skill after evidence operators return observations. Decide whether evidence is sufficient, whether second-pass retrieval is needed, or whether the answer must be bounded.

## Output Contract

- `sufficiency_level`: `sufficient`, `partial`, or `insufficient`.
- `missing_requirements`: missing tickers, years, source tiers, filing types, metric families, or market / industry fields.
- `specialist_evidence_gap_requests`: structured requests emitted by Specialists, Verifier, or prior reflection passes.
- `source_available`: whether the missing source family exists in inventory.
- `second_pass_requests`: only requests that can be compiled by the deterministic route compiler.
- `needs_user_clarification`: true only when the user scope is ambiguous or no source can disambiguate it.
- `bounded_answer_allowed`: true when current evidence can support a partial answer.
- `confidence_by_claim_type`: concise confidence labels by claim family.

## Gap Request Handling

- Treat `evidence_gap_requests` as requests for orchestration, not as user-facing caveats.
- Compile only actionable requests with known source families, bounded ticker scope, and a clear owner agent.
- Route `additional_company_scope` and `relationship_confirmation` to Universe / Relationship before more evidence operators when the current ticker scope is the blocker.
- Route `missing_metric` and `missing_source_family` to the SEC/8-K operator only when source inventory says the source exists.
- Route `market_field` and `industry_context` to the corresponding operator only when those context families are active.
- If the requested source is unavailable or the budget is exhausted, mark `bounded_answer_allowed=true` only when current evidence can support a clearly limited answer.

## Loop Rules

- Do not repeat an identical tool call.
- Do not rerun every source family for one missing requirement.
- Stop after no new rows and no closed coverage gaps.
- Keep loop-break reasons in trace, not in hidden reasoning.
