# Financial Evidence Label Protocol v0.1

This protocol defines how to judge whether a SEC evidence object supports a
single financial aspect. It is intentionally stricter than keyword matching and
separate from the model verifier's predicted label.

## Label Unit

The label unit is one `(query_id, facet, aspect, object_id)` row.

- `query_id`: the user-level finance task.
- `facet`: one sub-question planned for retrieval.
- `aspect`: one required fact inside the facet.
- `object_id`: one structured `TableObject`, `MetricObject`, or `ClaimObject`.

An object is judged only against the current aspect, not against all aspects in
the facet.

## Labels

### direct

Use `direct` when the object can be cited as evidence for the aspect without an
extra financial conversion step.

Required conditions:

- Same company and fiscal period as the task.
- Same business line, segment, metric, risk, or accounting term as the aspect.
- The object explicitly states the requested number, direction, driver, risk, or
  accounting condition.
- For table objects, the row/column context must be sufficient to identify the
  metric and period.

Examples:

- A table row that states AWS 2025 net sales were `$128.725 billion`.
- A claim that says Services net sales increased due to advertising, the App
  Store, and cloud services.
- A risk claim that explicitly mentions foundries, contract manufacturers, or
  limited supplier concentration when the aspect asks for that risk.

### partial

Use `partial` when the object is useful background but cannot be used as the
only citation for the aspect.

Common cases:

- It supports the same direction or business context but misses the exact metric
  or entity.
- It gives the number but not the definition needed by the aspect.
- It supports the broader facet but not the precise aspect wording.
- It requires a financial concept conversion, such as using ARR growth as
  evidence for subscription durability without stating the ARR definition.
- It is useful for synthesis context but should not be cited as the final proof
  for a claim.

### false

Use `false` when the object should not be used for the aspect.

Common cases:

- Wrong company, year, segment, metric, or accounting concept.
- Keyword overlap without support for the requested fact.
- Generic risk disclosure that does not connect to the requested risk.
- A table/claim that supports a different aspect in the same facet.

## Evidence Role

The label controls the evidence role:

- `direct` -> `citation`
- `partial` -> `background`
- `false` -> `reject`

For precision-gate evaluation, citation precision uses only `direct`. Broader
evidence-pool relevance may count `direct + partial`, but partial evidence must
remain marked as background before final synthesis.

## Current Review Scope

The first human-reviewed subset is not the full 730-row aspect pool. It reviews
the union of per-aspect top direct candidates selected by these policies:

- highest verifier confidence among Qwen direct predictions;
- highest BGE rerank score among Qwen direct predictions;
- highest BGE rerank score among Qwen direct predictions with confidence at
  least `0.90`.

This scope tests the practical serving question: if the system emits one top
direct evidence object per aspect, is that object citation-grade?
