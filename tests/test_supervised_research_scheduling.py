"""Use native static breakpoints for the first supervised development case.

These are host debug stop points, not a new workflow or production approval UI.
"""
import json
import pytest

from langgraph.checkpoint.sqlite import SqliteSaver

from sec_agent.agent_runtime.lead_research_graph import build_lead_research_graph
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticInput
from sec_agent.research_foundation.research_methods import get_research_method
from test_lead_research_graph import CATALOG, BRANCHES, _call, _task, _worker_result
from test_specialist_graph import _input
from test_workpaper_review_graph import _seed


@pytest.mark.parametrize("depth", ["focused", "integrated"])
def test_multi_paper_route_is_checked_before_dispatch(tmp_path, depth):
    value = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    workers = []
    def model(request):
        return _call(request, "DelegateResearchTasksAction", tasks=[_task("one"), _task("two")],
            execution_plan={"depth": depth,
                "rationale": "Two independent source-grounded papers are needed for the synthetic question.",
                "omitted_steps_reason": "No separate synthesis node is needed; source review and final verification remain.",
                "escalation_conditions": "Reassess the route if material cross-paper conflicts need distinct synthesis."})
    builder = build_lead_research_graph(expected_input=value, research_question="Synthetic route contract.",
        branch_catalog=CATALOG, allowed_branch_ids=BRANCHES, seed_workpapers={},
        model_turn=model, run_child=lambda *args: workers.append(args),
        require_all_branches=False, require_execution_plan=True)
    with SqliteSaver.from_conn_string(str(tmp_path/'route.sqlite')) as saver:
        graph = builder.compile(checkpointer=saver, interrupt_after=['lead_tools'])
        config = {'configurable': {'thread_id': 'route-check'}}
        graph.invoke(value.model_dump(mode='json'), config)
        state = graph.get_state(config)
        assert not workers
        if depth == "focused":
            assert not state.values['tasks'] and state.next == ('lead',)
            assert 'focused_route_requires_one_self_contained_workpaper' in state.values['tool_results'][0]['content']
        else:
            assert len(state.values['tasks']) == 2 and state.next == ('specialist', 'specialist')


def test_material_navigation_does_not_expand_question_with_internal_lineage():
    from sec_agent.research_foundation.task_attachments import task_material_catalog
    materials = [{'document_id': f'UPLOAD::{i}', 'name': f'original-{i}.html', 'kind': 'document',
        'sections': 4, 'needs_vision': False, 'project_origin': {'private_store': 'x'*2000,
        'source_dependencies': ['immutable-origin']*20}} for i in range(7)]
    catalog = task_material_catalog(materials)
    assert len(json.dumps(catalog)) < 1500
    assert [m['document_id'] for m in catalog] == [m['document_id'] for m in materials]
    assert all('project_origin' not in m for m in catalog)
    assert all(m['project_origin']['source_dependencies'] for m in materials)


def test_host_observes_plan_then_worker_results_without_replaying_lead(tmp_path):
    seed, requests, workers = _seed(), [], []
    value = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    def model(request):
        requests.append(request)
        assert '按证据推进的调度' in request['role_method']['content']
        return _call(request, 'DelegateResearchTasksAction', tasks=[_task()])
    def worker(task, dependencies, config):
        workers.append(task['task_id'])
        return _worker_result(task, seed)
    def builder():
        return build_lead_research_graph(expected_input=value, research_question='Synthetic scheduling only.',
            branch_catalog=CATALOG, allowed_branch_ids=BRANCHES, seed_workpapers={},
            model_turn=model, run_child=worker, require_all_branches=False, role_method=get_research_method('lead'))
    config = {'configurable': {'thread_id': 'supervised-case'}}
    path = str(tmp_path/'checkpoints.sqlite')
    with SqliteSaver.from_conn_string(path) as saver:
        graph = builder().compile(checkpointer=saver, interrupt_after=['lead_tools', 'collect_task_artifacts'])
        graph.invoke(value.model_dump(mode='json'), config)
        state = graph.get_state(config)
        assert state.next == ('specialist',)
        assert len(requests) == 1 and not workers
        assert state.values['tasks'][0]['task_id'] == _task()['task_id']
    # Explicit host continuation after inspection; no restart of paid planning.
    with SqliteSaver.from_conn_string(path) as saver:
        graph = builder().compile(checkpointer=saver, interrupt_after=['lead_tools', 'collect_task_artifacts'])
        graph.invoke(None, config)
        state = graph.get_state(config)
        assert state.next == ('lead',)
        assert len(requests) == 1 and workers == [_task()['task_id']]
        assert state.values['task_results'][0]['status'] == 'submitted'
