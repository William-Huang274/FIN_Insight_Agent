# Coverage Reflection Skill v0.1

Use this skill after evidence operators return observations. Decide whether evidence is sufficient, whether second-pass retrieval is needed, or whether the answer must be bounded.

## Output Contract

- `sufficiency_level`: `sufficient`, `partial`, or `insufficient`.
- `missing_requirements`: missing tickers, years, source tiers, filing types, metric families, or market / industry fields.
- `source_available`: whether the missing source family exists in inventory.
- `second_pass_requests`: only requests that can be compiled by the deterministic route compiler.
- `needs_user_clarification`: true only when the user scope is ambiguous or no source can disambiguate it.
- `bounded_answer_allowed`: true when current evidence can support a partial answer.
- `confidence_by_claim_type`: concise confidence labels by claim family.

## Loop Rules

- Do not repeat an identical tool call.
- Do not rerun every source family for one missing requirement.
- Stop after no new rows and no closed coverage gaps.
- Keep loop-break reasons in trace, not in hidden reasoning.
