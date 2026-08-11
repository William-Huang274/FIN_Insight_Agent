# FIN PRD Full Absorption And Program Plan Correction

Date: 2026-07-19

Status: `product_allocation_and_program_draft_pending_user_acceptance`

## Decision

Created `docs/product/FIN_PRD_FULL_ABSORPTION_AND_RELEASE_ALLOCATION_MATRIX_20260719.zh-CN.md` and corrected the FIN 0.1 Program Plan after the user identified that the six-block matrix over-emphasized the Agent integration gap.

The new allocation matrix explicitly covers:

- all five PRD product planes;
- all thirteen PRD functional modules;
- B0-B7;
- F01-F15;
- permanent non-goals;
- named release or track allocation for every deferred capability.

The FIN 0.1 six-block matrix now names absorbed PRD surfaces and named future interfaces. It also adds a bounded user-visible Graph drilldown to S3, distinguishes scoped exact Case/Run history from FIN 0.3 institutional memory, and keeps Data Room, Monitoring, Quant, multi-format delivery and enterprise governance attached to named roadmap entries rather than one generic deferred list.

## Boundary

- The allocation matrix owns product-to-release mapping only, not implementation progress.
- Program backlog v2.0 remains pending user acceptance and is not execution authority.
- ReleaseContract and FeatureScope have not yet been version-bumped.
- No runtime, model, provider, network, Case, Human review or release action occurred.
