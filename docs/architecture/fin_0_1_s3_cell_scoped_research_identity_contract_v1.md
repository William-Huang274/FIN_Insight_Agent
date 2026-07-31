# FIN 0.1 S3 Cell-scoped research identity contract v1

Date: 2026-07-23
Contract ref: `fin01.s3.cell_scoped_research_identity:v1`

## Purpose

Specialist-generated Claim and What-Would-Change IDs are local to one Program Cell. They are not globally unique research identifiers. This contract prevents downstream Lead, Writer, and Verifier joins from overwriting or rejecting valid records when different Cells reuse the same local ID.

The authoritative runtime identity is:

```text
(identity_kind, program_cell_id, local_id)
```

Supported `identity_kind` values are `claim` and `what_would_change`.

## Ownership and derivation

1. A Specialist Provider may emit a local `claim_id` or `task_id`.
2. The existing Specialist validator first validates that ID inside its exact Cell.
3. The runtime binds the validated local ID to the exact `program_cell_id` and derives a `CellScopedResearchRef`.
4. Lead, Writer, and Verifier Provider schemas and local validators consume the same three-field typed reference.
5. Provider-local IDs remain unchanged in the Specialist output. Validation aliases are internal-only and are never persisted as replacements for Provider IDs.

The shared policy lives in `apps/workbench/backend/application/bounded_agent_identity_policies.py`. Its `wire_schema`, `parse`, `derive_surface`, and `index_surface` methods are the common source for Provider-visible shape and local validation.

## Failure behavior

The contract fails closed for:

- duplicate local IDs inside one Cell;
- a raw local-only ID used as a cross-Cell reference;
- a duplicate scoped reference;
- wrong kind, wrong Cell, or malformed scoped references;
- an unknown scoped reference;
- malformed task-to-claim bindings or incorrect collision-count metadata.

The canonical safe telemetry family is `scoped_identity_contract`. It permits only:

```json
{
  "identity_kind": "claim | what_would_change",
  "failure_subtype": "closed enum",
  "failing_item_count": 1
}
```

Raw IDs, Cell IDs, digests, item indexes, answer text, arbitrary keys, and private reasoning are forbidden.

## Version and compatibility boundary

- Historical Specialist transports v1-v7, output-v3, admissions, failed Runs, and captured Provider answers are immutable.
- The Specialist wire shape remains v7 because the identity is derived after Cell-local validation.
- New downstream wire consumers are versioned as Research Lead v4 and Memo Writer v3.
- The end-to-end bounded output contract is v4 and requires the exact scoped identity contract binding.
- Historical admissions that did not explicitly set `scoped_identity_contract_ref` retain their prior digest payload shape.

## Deterministic acceptance

The implementation is accepted at fixture level only when all of the following pass:

- two Cells reuse one Claim local ID without collision;
- two Cells reuse one WWC local ID without collision;
- same-Cell duplicates fail closed;
- raw, unknown, wrong-kind, and wrong-Cell references fail closed;
- a non-NVDA, different-period, mixed Evidence/Numeric fixture remains valid;
- a fake Provider traverses six logical nodes with 12 calls and produces nine Artifact families;
- canonical telemetry persists the closed content-free shape and rejects a raw-ID extension.

This is engineering readiness, not a real Agent product result. A fresh exact Agent proof requires separate decision, admission, and execution authority.

## Verifier convergence status

As of 2026-07-25, the output-v4 Verifier request and local validator both
consume `CellScopedResearchIdentityPolicy`:

- Provider-visible `artifact_or_claim_refs` uses the three-field typed Claim
  wire schema rather than an ambiguous string;
- the local validator checks every ref against the exact scoped identity
  surface and rejects raw, unknown, wrong-kind, wrong-Cell, and duplicate refs;
- the current pre-Artifact Verifier supports Claim refs only; Artifact refs
  require a separately versioned post-render verification contract;
- deterministic digest and scope bindings remain locally owned, while the
  model supplies bounded semantic findings;
- disclosed unresolved conflicts and explicitly company-total,
  non-attributed metrics remain quality findings unless they create a material
  unsupported claim.

This convergence is zero-call and fixture-proven. It does not rewrite the
failed historical Run or establish a current nine-Artifact product.

## Fresh proof gate status

As of 2026-07-25, the post-convergence fresh proof decision is frozen under
`fin01.s3.layered_verifier_typed_ref_and_finding_disposition_fresh_agent_proof_decision:v1`.
The proof:

- derives a new WorkUnit, Attempt, ResearchRun, exact input, and prospective
  admission in a disposable clone;
- binds output-v4, profile-v4, ClaimFactLinkPolicy, scoped identity v1,
  Verifier state-machine v2, supervision v2, and the seven current code
  surfaces required by the exact path;
- requires exact typed Claim-ref membership and preserves L1 hard integrity;
- permits persisted L3/L4 findings only after L1 passes;
- still requires one coherent succeeded Run with six logical nodes, twelve
  Provider calls, and nine current Artifact families.

The proof step creates no admission or canonical execution state. Admission
issuance, consumption, exact-live execution, paired comparison, and owner
acceptance remain separately governed.
