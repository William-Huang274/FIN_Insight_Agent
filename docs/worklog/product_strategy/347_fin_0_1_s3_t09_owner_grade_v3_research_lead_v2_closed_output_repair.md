# FIN 0.1 S3-T09 Research Lead v2 closed-output repair

Date: 2026-07-23

## Outcome

Implemented the separately authorized zero-call Research Lead v2 contract. The Provider now emits only four bounded semantic members; the runtime derives the three canonical cell heads from the already validated Specialist bodies and digests. The canonical output remains output-v3 and Specialist transport remains v5.

This closes the known project-owned Lead capacity contract in fixtures. It does not complete T09 because no fresh real Run or complete nine-Artifact owner-grade product has been produced.

## Contract changes

- Added explicit `fin01.s3.bounded_agent.research_lead_owner_grade:v2`.
- Preserved historical Lead behavior and old admission digests when the new field is absent.
- Bound v2 only to Specialist transport v5 plus canonical output-v3.
- Kept full Specialist fact, claim, scope, qualification, gap and actionable-WWC bodies in the Lead input.
- Removed Provider responsibility for `cell_heads` and the duplicate digest map.
- Closed dependencies/conflicts/gaps at `1..3 / 0..3 / 1..4`.
- Enforced 320 Unicode characters per narrative field, 6000 Provider bytes and 8192 assembled bytes.
- Enforced Lead 1800 and aggregate 16800 output tokens under the unchanged USD 0.10 cap and retry=0.
- Added content-free parse/shape/cardinality/text/authority/capacity/assembly telemetry and canonical rejection of raw text or arbitrary fields.

## Verification

- Research Lead v2 plus historical transport-v5 suite: `28 passed`.
- Canonical runtime failure persistence suite: `18 passed`.
- Python compile: pass.
- Fake Provider positive path: 12 calls, six logical nodes and nine Artifacts.
- Minimum and maximum closed-cardinality fixtures fit both byte envelopes.
- Parse failure, length stop, Provider byte overflow, invalid shape/cardinality/text/authority and unsafe telemetry all fail closed.
- Total focused and canonical tests: `46 passed`.
- Real model, Provider, network, admission, WorkUnit, Attempt, ResearchRun, Artifact, comparison and Human Review counts: all zero.

## Boundary and next action

RC-P36-040 is fixture-repaired, not live-proven. RC-P36-037 and S3-T09 remain blocked until a separately governed fresh proof produces a complete product suitable for paired comparison and owner acceptance.

The only next item is `S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V2-FRESH-AGENT-PROOF-DECISION`. It is not authorized by this implementation.
