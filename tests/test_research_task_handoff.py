"""Delegation uses real shared tools; fixtures never imply autonomous Lead proof."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.agent_runtime.specialist_composition import (
    SpecialistAgenticCompositionError, _bind_research_task,
    open_specialist_scripted_qualification_composition,
)
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticInput
from sec_agent.agent_runtime.deepseek_structured_agents import _project_agentic_specialist_request
from test_specialist_graph import _input
from test_workpaper_review_graph import _seed


def _assignment(branch="Q1_ISSUER_TRUTH", dependencies=(), capability="capability:dell:reviewed-evidence"):
    return {"task_id": "task:dell:price-financial-transmission", "owner_role": "supply_price_analyst",
            "objective": "核查供给和价格变化传导到 Dell 财务兑现的机制，明确观测与推断的界线。",
            "dependency_ids": list(dependencies), "coverage_obligation_ids": [branch],
            "success_criteria": ["结合上游底稿，自主读取来源；不将其他 Agent 的断言当成事实。"],
            "requested_capability_refs": [capability], "expected_output_kinds": ["branch_notebook", "claim_ledger"],
            "materiality": "high", "status": "planned"}


def test_assignment_is_bound_without_inheriting_authority_counts_or_source_observations():
    base = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    seed = _seed()
    original = deepcopy(seed)
    dep = seed["task"]["task_id"]
    assignment = _assignment(dependencies=(dep,))
    assignment["objective"] += "核查" * 1100  # Valid canonical TaskSpec must not be silently truncated.
    bound = _bind_research_task(base, assignment, {dep: seed})
    assert bound.task.objective == assignment["objective"]
    assert bound.task.task_id == assignment["task_id"] and bound.agent_id != base.agent_id
    assert bound.task.evidence_requests == base.task.evidence_requests
    assert bound.required_route_obligation_ids == base.required_route_obligation_ids
    assert bound.l0_context == base.l0_context
    assert 'workpaper' not in bound.task_context['dependency_workpapers'][0]
    assert bound.task_context['dependency_workpapers'][0]['read']['tool'] == 'ReadDependencyWorkAction'
    assert bound.task_context['dependency_workpapers'][0]['read']['arguments']['task_id'] == dep
    assert "notebook" not in bound.task_context["dependency_workpapers"][0]
    assert seed == original


def test_dependency_reader_keeps_analysis_optional_and_restores_original_receipts():
    from sec_agent.agent_runtime.specialist_handoff import DependencyReader
    from test_research_session import _new_worker_fixture
    seed = _new_worker_fixture()
    dep = seed['task']['task_id']
    reader = DependencyReader({dep: seed})
    original = deepcopy(seed)
    catalog, restored = reader({'task_id': dep, 'section': 'sources', 'limit': 12})
    assert not restored
    assert 'thesis' not in json.dumps(catalog)
    source_ids = [row['source_id'] for row in catalog['sources']]
    for row in catalog['sources']:
        assert row['read']['arguments'] == {'task_id': dep, 'section': 'handoff', 'source_ids': [row['source_id']]}
    _, page_originals = reader(catalog['read_page']['arguments'])
    assert page_originals
    materials, restored = reader({'task_id': dep, 'section': 'handoff', 'source_ids': source_ids, 'limit': 12})
    assert restored and all(obs in seed['notebook']['observations'] for obs in restored)
    assert 'read_current_' not in json.dumps(materials)
    analysis, observations = reader({'task_id': dep, 'section': 'analysis'})
    assert not observations
    assert seed['final_submission']['thesis'] in json.dumps(analysis, ensure_ascii=False)
    assert seed == original
    with pytest.raises(ValueError, match='unknown_dependency'):
        reader({'task_id': 'unassigned', 'section': 'sources'})


def test_native_dependency_read_is_citable_without_inheriting_author_interpretation():
    from sec_agent.agent_runtime.specialist_handoff import DependencyReader
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
    from test_specialist_graph import _ToolPorts
    from test_research_session import _new_worker_fixture
    seed = _new_worker_fixture()
    dep = seed['task']['task_id']
    base = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    initial = _bind_research_task(base, _assignment(dependencies=(dep,)), {dep: seed})
    calls = []
    def turn(request):
        calls.append(request)
        if len(calls) == 1:
            return {'action': 'native_tool_batch', 'context_digest': request['context_digest'], 'tool_calls': [
                {'id': 'dependency-read', 'name': 'ReadDependencyWorkAction', 'args': {
                    'action': 'read_dependency_work', 'context_digest': request['context_digest'],
                    'task_id': dep, 'section': 'handoff', 'limit': 12, 'reason_summary': '读取原始材料'}}]}
        return {'action': 'request_human_review', 'context_digest': request['context_digest'],
                'reason_summary': '离线接口验证结束', 'blocker_code': 'offline_complete'}
    ports = _ToolPorts()
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=ports.evidence, finance_tool=ports.finance,
        dependency_reader=DependencyReader({dep: seed}))).compile()
    result = graph.invoke(initial.model_dump(mode='json'))
    assert len(calls) == 2 and not ports.calls
    assert result['notebook']['observations'] == seed['notebook']['observations']
    assert result['notebook']['tool_action_count'] == 1
    wire = _project_agentic_specialist_request(calls[0])
    assert wire['task_context']['dependency_workpapers'][0]['read']['arguments']['task_id'] == dep


def test_fresh_formation_exposes_all_saved_sources_without_old_author_or_stop_guidance():
    from sec_agent.agent_runtime.specialist_handoff import DependencyReader, bind_saved_materials
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
    from test_specialist_graph import _ToolPorts
    from test_research_session import _new_worker_fixture
    old = _new_worker_fixture()
    task_id = old['task']['task_id']
    old['lead_assistance_history'] = [{'next_action': 'LEGACY_STOP_READING_SENTINEL'}]
    old['research_working_state'] = {'thesis': 'LEGACY_NOTE_SENTINEL'}
    assignment = _assignment()
    assignment['task_id'] = task_id
    initial = _bind_research_task(SpecialistAgenticInput.model_validate_json(json.dumps(_input())), assignment, {})
    initial = bind_saved_materials(initial, old)
    reader = DependencyReader({task_id: old}, source_only_tasks=(task_id,))
    sources, _ = reader({'task_id': task_id, 'section': 'sources', 'limit': 12})
    material, observations = reader({'task_id': task_id, 'section': 'handoff', 'limit': 12})
    assert material['source_count'] == sources['source_count']
    assert observations == old['notebook']['observations']
    assert 'author_analysis' not in json.dumps(material)
    for section in ('overview', 'analysis', 'assignment'):
        with pytest.raises(ValueError, match='source_only'):
            reader({'task_id': task_id, 'section': section})
    calls = []
    def model(request):
        calls.append(request)
        return {'action':'request_human_review', 'context_digest':request['context_digest'],
                'reason_summary':'Offline input inspection complete.', 'blocker_code':'fixture_complete'}
    ports = _ToolPorts()
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=model, evidence_tool=ports.evidence, finance_tool=ports.finance,
        dependency_reader=reader, working_state_enabled=True)).compile()
    graph.invoke(initial.model_dump(mode='json'))
    wire = _project_agentic_specialist_request(calls[0])
    text = json.dumps(wire, ensure_ascii=False)
    assert 'LEGACY_' not in text and old['final_submission']['thesis'] not in text
    assert calls[0]['notebook']['model_turn_records'] == []
    assert calls[0]['notebook']['observations'] == []
    assert 'read_dependency_work' in calls[0]['allowed_actions']
    assert wire['task_context']['saved_source_materials']['read']['arguments']['task_id'] == task_id
    changed = deepcopy(old)
    changed['task']['task_id'] = 'another_task'
    with pytest.raises(ValueError, match='saved_material_task_scope_mismatch'):
        bind_saved_materials(initial, changed)


@pytest.mark.parametrize("defect", ["scope", "status", "missing_dependency", "identity", "as_of", "capability", "authority", "unfinished"])
def test_invalid_assignment_fails_before_model_or_data_tools(defect):
    base = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    seed = _seed()
    dep = seed["task"]["task_id"]
    task, dependencies = _assignment(dependencies=(dep,)), {dep: seed}
    if defect == "scope":
        task["coverage_obligation_ids"] = ["Q5_SUPPLY_AND_PRICE"]
    elif defect == "status":
        task["status"] = "completed"
    elif defect == "missing_dependency":
        dependencies = {}
    elif defect == "identity":
        task["dependency_ids"] = ["task:invented"]
        dependencies = {"task:invented": seed}
    elif defect == "as_of":
        seed["task"]["research_as_of"] = "2027-01-01T00:00:00Z"
    elif defect == "capability":
        task["requested_capability_refs"] = ["capability:arbitrary-shell"]
    elif defect == "authority":
        task["required_authority_refs"] = ["authority:admin"]
    else:
        seed["phase"] = "ready_for_model_decision"
    with pytest.raises((ValueError, SpecialistAgenticCompositionError)):
        _bind_research_task(base, task, dependencies)
