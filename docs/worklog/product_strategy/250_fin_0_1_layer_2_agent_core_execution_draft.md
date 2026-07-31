# FIN 0.1 Layer 2 Agent Core Execution Draft

Date: 2026-07-19

Status: `docs_only_discussion_draft`

## Decision

Created `docs/architecture/repository/FIN_0_1_LAYER_2_AGENT_CORE_EXECUTION_DRAFT_20260719.zh-CN.md` as the second-layer child of the FIN 0.1 product-mainline draft.

The draft converts the Agent Core discussion into a bounded migration plan:

- freeze one `Fin01ResearchRuntime`, versioned execution profile, exact ResearchRun and structured EventTrace;
- retain the current P36 deterministic product path as an explicitly labelled fallback;
- absorb the historical LangGraph as an Agent fixture/shadow adapter;
- runtime-enable the existing Agent and Skill registries;
- migrate three high-value P36 cells before expanding to the remaining cells;
- route Workbench exclusively through the unified Runtime;
- require exact Agent/Skill/Tool/Graph trace and prevent fallback/Agent result confusion.

The 2026-07-19 discussion then froze the target Research Lead semantics:

- Agentic Research is an observation-driven plan/dispatch/observe/replan/repair/stop loop, not merely dynamic permissions or model/tool calls;
- Lead decisions are versioned structured objects and private model chain-of-thought is neither persisted nor displayed;
- Lead may reorder research, select admitted capabilities, request evidence/repair, reopen on cross-cell conflict, stop and synthesize;
- Lead may not change Case scope, exceed permission/budget, promote Evidence, override deterministic Numeric, bypass review/release authority or grant Writer source access;
- the first Agent vertical remains `demand_signal`, `revenue_capture` and `thesis_counterevidence`, covering demand, value/profit capture and counterevidence/What-Would-Change;
- `L2-D02-DecisionSurfaceMutationAuthority` is frozen as `bounded_run_overlay_with_human_versioned_material_revision`: accepted DecisionSurface versions are immutable, Lead autonomously manages a versioned run overlay and bounded investigation branches, and top-level or semantic changes require an exact revision proposal plus Human Review and a child ResearchRun.

## Evidence Baseline

- Agent Registry: 17 definitions, registry validation pass.
- Skill Registry: 16 skill files and 20 role bindings.
- Existing focused tests: 33 passed and 1 stale source-family assertion failed.
- Current Workbench research path remains deterministic and disconnected from the historical Agent runtime.
- Current actual DeepSeek/model/provider call count remains zero; this update is contract documentation only.
- No Runtime, state-machine or UI implementation was performed for `L2-D02`; implementation remains pending the Agent topology and handoff decision.
- `L2-D03-AgentTopologyAndHandoff` is frozen as `stable_domain_specialists_with_lead_mediated_handoffs`: Research Lead plus five stable Domain Specialists and bounded Writer/Verifier remain reasoning agents; six retrieval definitions become Evidence Operators; coverage reflection, judgment aggregation and rendering become deterministic services.
- The first three cells map dynamically to primary and conditional Specialists. Specialist-to-Specialist private calls are forbidden; every structured task/result handoff returns through Runtime and Lead.
- No Agent registry, historical graph, Runtime or Workbench code was changed for `L2-D03`; implementation remains pending later execution authorization.
- `L2-D04-SkillRuntimeContract` is frozen as `versioned_runtime_consumed_skillpacks_with_policy_separation`: mandatory policies cannot be disabled, Role Core Skills follow exact Agent versions, and Lead selects at most two compatible Optional Skills from the frozen ExecutionProfile allowlist.
- Existing operator, coverage, aggregation and renderer prompt fragments are reassigned to their Runtime service policies; Skill cannot grant tools, data, models, network, budget, memory or authority.
- Current `research_skills.py` remains a static Markdown loader. SkillDefinitionVersion, bounded SkillPack compilation, preflight, trace and runtime-consumption proof remain unimplemented.

## Boundaries

- No runtime or frontend code changed.
- No existing release/machine contract authority changed.
- No model, network, paid, commercial-data or operational execution occurred.
- No real business Case mutation or release admission was authorized.
- The next discussion layer is Agentic Search, Evidence, RAG/SQL/Graph.
