# ADR: Point 02 New-Lane Authority And Rollback Contract

## Status

Accepted for P02.0 contract and dependency freeze only. It does not create a store, flag, authority, approval, receipt, or runtime lane.

## Decision

Point 02 will use one future `point02_new_lane` only after its separately authorized implementation point. The lane is a consumer of Point 01 canonical contracts; it is not a replacement source of truth and cannot change legacy authority.

| Boundary | Frozen contract | Owner | Current status |
| --- | --- | --- | --- |
| Authority | `legacy_global_authority=retained`; the future lane is shadow/internal until a future case-scoped admission | TECH_06 | retained / no admission |
| Canonical store | Future lane may use a separately named, case-scoped canonical projection store with versioned records and append-only events | TECH_06 | design only; no store opened |
| Object store | Future lane may store only versioned, redacted artifact envelopes addressed by digest; it may not persist raw prompts, secrets, or unredacted observations | TECH_06 | design only; no object root created |
| Feature flag | `point02_new_lane_enabled`, default `false`, scoped to an explicit tenant/project/case and release profile | TECH_06 | design pin only; no flag provider invoked |
| Product routes | Routes read canonical projections through the API only; browser code never reads SQLite, object roots, or Python objects | TECH_09 | contract only |

## Rollback

Rollback is `disable flag -> stop new-lane commands -> render legacy-backed read models -> preserve append-only new-lane events/artifacts for audit`. It must not rewrite legacy records, mutate a global legacy authority label, delete audit evidence, or silently replay an in-flight command. A future implementation must expose an idempotent typed stop for requests that arrive after flag disable.

## Non-goals And Hard Blockers

- P02.0 does not grant a persistent-store write, object-store write, authority transition, approval, receipt, runtime execution, or production cutover.
- `REL-PROD-001-RG1-POINT01-OPERATIONAL-VERTICAL-PATH` remains a non-bypassable release blocker: exact entry-to-clean-child identity, one bounded operational vertical run, and persisted actual/oracle/reviewer/Workbench outputs are required before P07.5.
- The Point 01 consumed receipt remains historical and non-replayable. This ADR is not a replacement receipt or a route around that stop.
