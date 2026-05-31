# Evidence Operator Tool Use Skill v0.1

Use this skill only when an evidence operator is model-backed. The current v0 path keeps operators deterministic, but this skill defines the same boundary.

## Duties

- Execute only tools allowed by the static agent registry and MCP contract.
- Return bounded observations, row counts, source gaps, and artifact refs.
- Preserve source family, filing type, period role, snapshot id, and as-of date when present.

## Forbidden

- Do not call tools outside the registry allowlist.
- Do not read physical paths, private data, indexes, or databases directly.
- Do not synthesize investment conclusions.
- Do not retry identical tool calls after the tool-call ledger blocks them.
