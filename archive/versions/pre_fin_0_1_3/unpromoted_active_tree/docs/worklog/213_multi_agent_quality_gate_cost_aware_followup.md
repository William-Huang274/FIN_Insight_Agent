# 213 Multi-agent Quality Gate / Cost-aware Follow-up

Date: 2026-06-01
Branch: `codex/api-model-call-architecture`

## Scope

This iteration followed the post-Q14 repair order:

1. Banking runtime ledger / exact-value rows.
2. Specialist v0.3 ClaimCard ranker.
3. Aggregator `memo_thesis_plan`.
4. Memo Writer thesis-led output.
5. Research Lead cost-aware activation.
6. Relationship graph edge schema deepening.
7. Verifier quality gate.

Earlier in the same repair sequence, banking runtime ledger extraction and exact-value rows were fixed so banking sector-depth retrieval no longer collapses to `runtime_ledger_rows=0` when SEC context tables include tax text or mixed bank table units. This pass completed the later control-plane fixes.

## Implemented Changes

- Research Lead deterministic routing is now cost-aware:
  - `standard_memo` activates only requested analyst lenses instead of always opening Fundamental / Market / Risk.
  - `deep_research` keeps Fundamental + Industry/Relationship as primary and activates Market / Risk only when the query or source contract requests those lenses.
  - Activation plans include `metadata.cost_aware_activation` with policy, active counts, and agent role mapping.
- LLM Research Lead sector-depth normalization no longer forces all optional specialists. It promotes relationship/sector-depth scope to `deep_research`, but only adds Market / Risk when the request or source contract requires them.
- Specialist execution now honors `primary | supporting | conditional | low` priorities:
  - primary/supporting specialists run;
  - conditional specialists run only when matching evidence rows or explicit intent exist;
  - skipped conditional specialists are recorded in `specialist_activation_decisions` and `specialist_route_results` for runtime audit.
- Relationship graph rows now carry edge schema v0.2:
  - `edge_id`, `from_ticker`, `to_ticker`, `edge_direction`, `mechanism`, `metric_links`, `source_pack_id`, `source_record_ref`, `claim_scope`.
  - `UniverseRelationshipPlan` validator now checks edge endpoints / ids while preserving hypothesis-only scope.
  - Industry data views preserve edge metadata in bounded rows and relationship summaries.
- Verifier deterministic gate now checks memo quality contract, not only safety:
  - If a verified judgment has `memo_thesis_plan`, draft memo must carry it.
  - Draft memo must declare `memo_generation_policy = thesis_led_claim_cards_v0_1`.
  - High-rank ClaimCard evidence coverage warnings are surfaced without allowing the LLM verifier to override deterministic hard failures.

## Validation

Passed:

- `python -m pytest tests/test_multi_agent_activation_plan.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_contracts.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_memo_llm_repair.py -q`
  - `103 passed`
- `python -m pytest tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_evidence_requirements.py tests/test_sec_agent_ledger_store.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_output_quality_audit.py -q`
  - `44 passed`
- `python -m pytest tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_agent_registry.py tests/test_sec_agent_langgraph_orchestrator.py -q`
  - `43 passed`
- `python -m compileall src\sec_agent tests`
- `git diff --check`

Smoke check:

- Banking sector-depth / relationship query routes to `deep_research` with Fundamental + Industry/Relationship primary only.
- Full AI capex query with market reaction and counterevidence still activates all four specialists with Fundamental / Industry primary and Market / Risk supporting.
- Fundamentals-only peer query activates only Fundamental specialist.

## Residual Risk

- This pass did not run a new paid DeepSeek full-chain evaluation. The changes are deterministic/control-plane level and covered by unit and graph tests.
- Next real evaluation should compare token spend and memo quality before/after `cost_aware_specialist_activation_v0_1`, especially on banking and utilities sector-depth cases.
- Verifier quality gate is intentionally stricter only when `memo_thesis_plan` exists. Older/manual judgment fixtures without a thesis plan emit warnings, not hard failures.

## Sensitive Information

No API key, SSH password, private token, or secret value was written to this document or to code.
