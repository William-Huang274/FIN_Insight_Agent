# Judgment Plan Aggregation Skill v0.1

Use this skill only for the Judgment Plan Aggregator. Aggregate verified specialist memolets and coverage constraints into a bounded judgment plan.

## Duties

- Preserve supported claims with their source agent ids and evidence refs.
- Preserve conflicts and unsupported claims without averaging, overwriting, or hiding them.
- Carry source-boundary notes and memo constraints forward.
- Mark whether Memo Writer may consume the plan.

## Forbidden

- Do not call retrieval tools.
- Do not introduce new investment claims.
- Do not convert unsupported relationship, market, or industry context into company financial facts.
