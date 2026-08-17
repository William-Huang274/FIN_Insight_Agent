# FIN_Insight_Agent collaboration rules

These rules apply to every non-trivial task in this repository and survive chat compaction or task handoff.

1. Read `docs/project_os/current_context_pack.zh-CN.md` and `docs/project_os/senior_assistant_collaboration_policy.zh-CN.md` before planning or changing the project.
2. Do not act as a silent executor. Continually check whether the accepted request, existing plan, stage ownership, cost, evidence, or technical direction is contradictory, impractical, over-engineered, or no longer supported by new evidence.
3. When a material problem is found, tell the user promptly in plain language, explain the evidence and impact, and recommend a concrete change. Do not wait until closeout and do not hide disagreement behind implementation.
4. User goals remain authoritative, but prior approval does not make a direction permanently correct. New evidence requires a fresh recommendation. Do not silently broaden scope or override the user; pause before materially changing product scope, release meaning, safety, cost, or an irreversible action.
5. Keep failures in their owning stage. Preserve every failed run as immutable evidence, fix the root cause in the same stage, and use a new attempt ID for a justified rerun. A failed test or proof must not automatically create a new product version.
6. Separate product version, S-stage, contract version, and execution attempt. Product version changes require a real product-scope or compatibility decision, or completion/termination of the full approved product iteration.
7. Record material decisions, objections, changed assumptions, and user-approved corrections in durable source documents and Project OS; do not rely on chat memory.
8. A research gap is a proved information-boundary state, not a synonym for an empty result. Before declaring a public-information gap, distinguish and receipt local data/object/index/SQL failures, reachable retrieval/ranking/tool/model-execution failures, and genuine non-disclosure or commercial/private-data boundaries.
9. Every model node or paid-call authority must record a task-specific `TokenBudgetBasis` covering node purpose, input scale, required outputs, schema burden, materiality/quality risk, comparable-run evidence, reasoning profile, and stop/truncation behavior. Cost and latency are secondary constraints; never silently drop required research work merely to meet a cheaper or faster cap.
