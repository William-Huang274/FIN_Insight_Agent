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
