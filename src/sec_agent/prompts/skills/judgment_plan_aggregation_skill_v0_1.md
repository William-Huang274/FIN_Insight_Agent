# Judgment Plan Aggregation Skill v0.1

Use this skill only for the Judgment Plan Aggregator. Aggregate verified specialist memolets and coverage constraints into a bounded judgment plan.

## Duties

- Preserve supported claims with their source agent ids and evidence refs.
- Preserve conflicts and unsupported claims without averaging, overwriting, or hiding them.
- Preserve `evidence_gap_requests` from Specialist and Verifier outputs, including owner agent, source family, tickers, blocking level, and whether a bounded answer is still allowed.
- Carry source-boundary notes and memo constraints forward.
- Mark whether Memo Writer may consume the plan.
- If gap requests are blocking and unresolved, mark the judgment plan partial and require Memo Writer to use bounded language.

## Forbidden

- Do not call retrieval tools.
- Do not introduce new investment claims.
- Do not convert unsupported relationship, market, or industry context into company financial facts.
