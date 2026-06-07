# Verification Skill v0.1

Use this skill to inspect a memo or specialist output against bounded evidence. Do not generate new investment views.

## Checks

- Every numeric company financial fact must map to ledger rows or supported structured evidence.
- Market claims must carry `snapshot_id`, `as_of_date`, and field refs.
- Industry claims must remain context-only and carry provider / source-family metadata when available.
- Management commentary must not be rewritten as audited fact.
- Named facts, products, customers, suppliers, or relationships must be supported by evidence or marked unsupported.
- Period roles must not be mixed silently.

## Output

- Pass / fail status.
- Unsupported claim count.
- Repair instructions when repairable.
- Bounded-answer fallback when not repairable.
- `repair_route`: `repair_from_existing_claim_cards`, `needs_second_pass_retrieval`, `needs_universe_rescope`, or `must_bound_answer`.
- `evidence_gap_requests` when the memo cannot be repaired from existing ClaimCards and needs Coverage / Reflection, Universe / Relationship, or an operator to close a specific gap.

## Gap Escalation

- Use `needs_second_pass_retrieval` only when a source family exists and the missing item is specific enough to compile.
- Use `needs_universe_rescope` when the memo makes or needs a claim about companies outside the current bounded scope.
- Use `must_bound_answer` when the source is unavailable, budget is exhausted, or the claim would require model memory.
- Do not add new investment views while describing the gap.
