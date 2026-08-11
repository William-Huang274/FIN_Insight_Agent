# Agent Graph vNext G1/G2 Inventory And Plan Reflection

Date: 2026-06-12

## Problem

User asked to start implementing the `06_implementation_sequence_and_acceptance_gates.zh-CN.md` execution order. G0 was already frozen in the previous commit, so this pass starts with G1 and G2.

## Decision

Implement G1 and G2 as bounded runtime contracts before changing evidence fusion, second pass, web operator, or specialist roster. This keeps default retrieval behavior stable while making source authority and plan drift visible before any retrieval node runs.

## Work Completed

- Extended static source families to include `company_product_evidence_graph`, `public_source_context`, `live_public_web_context`, and `milvus_semantic`.
- Mapped `milvus_semantic` route to explicit `milvus_semantic` source family while preserving its semantic-recall-only boundary.
- Added `inventory_brief_v0.2` fields:
  - `source_family_availability`
  - `source_family_authority`
  - `known_gap_type_counts`
  - `milvus_runtime`
  - `live_public_web_context`
  - `playbook_candidates`
- Kept Research Lead inventory compact by compressing full `project_source_inventory_v0.1` into the v0.2 brief inside `build_agent_data_view(...)`.
- Added deterministic `plan_reflection_gate(...)` and inserted graph node `plan_reflection_gate` after `validate_activation_plan`.
- Added Research Lead evidence-route alignment so LLM-emitted routes such as `milvus_semantic`, market, or industry routes extend activation source/operator contracts before validation.
- Gate now fails closed before retrieval for:
  - required source family unavailable or missing from inventory
  - `milvus_semantic` requested while Milvus is unavailable
  - `live_public_web_context` requested without web scope policy
  - selected playbook or industry schema inconsistent with inventory candidates
  - focused answer attempting relationship/deep-research scope
  - deep research relationship route missing rationale
- Added `plan_reflection` summary to `multi_agent_summary.json`.

## Evidence

- `python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_activation_plan.py tests/test_multi_agent_agent_registry.py tests/test_research_skills.py -q` -> `68 passed`.
- `python -m pytest tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_specialist_llm.py tests/test_project_inventory_source_inventory.py -q` -> `80 passed`.
- `python -m pytest tests/test_multi_agent_agent_registry.py tests/test_project_inventory_source_inventory.py tests/test_multi_agent_evidence_requirements.py tests/test_research_skills.py -q` -> `34 passed`.
- `python -m compileall src/sec_agent/multi_agent_runtime.py src/sec_agent/langgraph_orchestrator.py src/sec_agent/project_inventory.py src/sec_agent/agent_registry.py src/sec_agent/agent_contracts.py src/sec_agent/research_lead_llm.py` -> pass.

## Follow-Up

- G3 remains next: Evidence Fusion Selector vNext should emit authority-labeled bundles and a first-class `BoundedGapRegister`.
- G4 should then split second pass into diagnosis, repair plan, hard gate, targeted executor, and delta audit.

## Safety Notes

- No raw rows, private paths, index paths, or API credentials are written to Research Lead compact inventory.
- Milvus remains cloud/local/unavailable capability metadata only; unavailable Milvus is not mocked as usable.
- Live web is only policy metadata at this stage; no browsing operator was introduced.
