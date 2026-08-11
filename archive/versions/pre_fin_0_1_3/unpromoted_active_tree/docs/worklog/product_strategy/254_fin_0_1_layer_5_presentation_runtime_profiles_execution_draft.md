# FIN 0.1 Layer 5 Presentation / Runtime Profiles Execution Draft

Date: 2026-07-19

Status: `docs_only_discussion_draft`

## Decision

Created `docs/architecture/repository/FIN_0_1_LAYER_5_PRESENTATION_RUNTIME_PROFILES_EXECUTION_DRAFT_20260719.zh-CN.md` after the user approved D11 and D12.

`L5-D11-WriterVerifierRoleBoundary` is frozen as `bounded_presentation_agent_with_independent_layered_verification`:

- Writer remains a bounded presentation agent that consumes frozen Judgment/Claim/What-Would-Change/WriterBrief/citation refs;
- Writer has no retrieval, source, raw Candidate or business-head write authority;
- Writer emits CanonicalPresentationModel, SurfaceClaim lineage, drafts and typed PresentationGap objects;
- verification is separated into deterministic integrity, semantic fidelity, financial coherence and visual layers;
- verifiers report findings and earliest repair owners but do not rewrite research truth;
- machine verification never implies Human acceptance or release admission.

`L5-D12-ExecutionProfilesAndFailureTruth` is frozen as `one_runtime_multiple_explicit_profiles_without_silent_substitution`:

- deterministic fallback, Agent fixture shadow, bounded Agent internal and release candidate use one Fin01ResearchRuntime and exact Run/Trace/artifact contracts;
- Agent failure remains failed, partial or typed-stop and cannot be overwritten by deterministic output;
- an explicitly requested fallback creates a separate child run with distinct profile, identity, artifact heads and UI labels;
- deterministic parser/numeric/gate/render services are allowed inside Agent profiles when explicitly traced, but fixed Judgment/Evidence replacement is prohibited;
- FIN 0.1 Agent claims require bounded Agent internal proof, while release evidence requires a frozen release candidate.

## Boundary

- No runtime, Writer, Verifier, frontend, model, provider, network, data or Case implementation changed.
- No paid call, real Case mutation, Human attestation, release candidate run or production action occurred.
- D13 and D14 remain under discussion.
