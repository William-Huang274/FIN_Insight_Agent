# FIN 0.1 Layer 4 Financial Judgment Execution Draft

Date: 2026-07-19

Status: `docs_only_discussion_draft`

## Decision

The Layer 3 draft now records D07 as a two-level contract:

- D07-A freezes claim-scoped, symmetric promotion, immutable lineage and Writer/Judgment authority boundaries;
- D07-B keeps evidence combinations, claim-strength thresholds and counterevidence materiality as versioned Cell/ClaimType policies that require real-case and Human Review calibration.

Created `docs/architecture/repository/FIN_0_1_LAYER_4_FINANCIAL_JUDGMENT_EXECUTION_DRAFT_20260719.zh-CN.md` and froze `L4-D08-SpecialistJudgmentContract` as `structured_financial_judgment_with_bounded_narrative_and_lead_cross_cell_synthesis`:

- Specialist output separates accepted facts, bounded mechanism explanation and professional judgment;
- the three launch cells use different financial reasoning chains instead of a common summary template;
- cannot-infer, counterevidence, assumptions, gaps and What-Would-Change remain first-class output;
- Lead owns cross-cell synthesis while Specialist cannot rewrite other cells, Evidence/Numeric heads or Writer admission;
- Workpaper and Report share exact Claim/Judgment lineage but serve different product purposes.

`L4-D09-ContextAndMemoryAllocation` is frozen as `role_scoped_reconstructable_context_with_registry_governed_memory`:

- one ContextEngine compiles exact role-specific, replayable input plans;
- Lead, Specialist, Evidence Operator, Writer, Verifier and Human Reviewer receive distinct minimum-necessary context;
- progressive disclosure preserves research depth while compaction cannot drop identity, permission, counterevidence, gaps, numeric boundaries or no-source policy;
- memory remains a registry-governed prior/reference, and agents can only submit MemoryWriteCandidate objects.

`L4-D10-RepairConcurrencyInvalidationAndStop` is frozen as `owner_routed_targeted_repair_with_snapshot_isolated_parallelism_and_materiality_based_invalidation`:

- repair routes to the earliest faulty owner and must add a changed input, route or verifiable hypothesis;
- independent read/candidate work may run in parallel, while each business head retains one authoritative writer;
- every WorkUnit pins exact versions/context/permission and stale late output is quarantined;
- PackChangeSet plus dependency/materiality contracts select continue, validate, checkpoint rebase or cancel/supersede;
- stop is based on acceptance, marginal value, exhaustion, permission/budget, repeated failure fingerprints or Human escalation, not a global one-repair rule.

## Boundary

- No runtime, Specialist, ContextEngine, repair, frontend or data implementation changed.
- No model, network, provider, paid data, Evidence promotion, canonical Case mutation or release action occurred.
- D11 and D12 remain under discussion.
