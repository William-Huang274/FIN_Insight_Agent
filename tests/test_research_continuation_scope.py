"""Offline recovery authority, real phase wiring; no financial quality claim."""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from langgraph.graph import StateGraph, START, END
from pydantic import SecretStr

from sec_agent.agent_runtime.execution_options import ExecutionOptions, execution_from_config
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticInput, SpecialistNativeToolBatch
from sec_agent.agent_runtime.research_graph_contracts import RuntimeReceipt, canonical_sha256
from test_lead_research_graph import _task, _call, _stop, _graph, _seed, _worker_result, BRANCHES
from test_specialist_graph import _input


def test_explicit_scope_survives_native_run_configuration():
    from apps.workbench.backend.api.v1.research_studio import run_configuration
    assert ExecutionOptions().continuation_scope == 'original_question'
    old = execution_from_config({'configurable': {'finsight_execution': {'mode': 'auto'}}})
    assert old.continuation_scope == 'original_question'
    selection = ExecutionOptions(mode='auto', continuation_scope='original_plan')
    config = asyncio.run(run_configuration(None, {'metadata': {'execution': selection.model_dump()}}))
    assert execution_from_config(config) == selection


@pytest.mark.parametrize('bounded', [False, True])
@pytest.mark.parametrize('has_seed', [False, True])
def test_native_phase_recovery_scope_controls_both_planner_and_worker(monkeypatch, tmp_path, bounded, has_seed):
    from sec_agent.agent_runtime import research_session_runtime as runtime
    seed = _worker_result(_task('saved'), _seed())
    original = deepcopy(seed)
    unfinished = _task('unfinished', BRANCHES[1], (seed['task']['task_id'],) if has_seed else ())
    extra = _task('gap', BRANCHES[0], (seed['task']['task_id'],) if has_seed else ())
    value = SpecialistAgenticInput.model_validate_json(json.dumps(_input()))
    requests, workers = [], []
    plan = {'depth': 'integrated', 'rationale': 'Fill a gap in the original question using saved work.',
            'omitted_steps_reason': 'No evidence or review omitted.', 'escalation_conditions': 'Report unresolved scope if authority is bounded.'}

    def model(request):
        requests.append(deepcopy(request))
        assert request['research_question'] == 'Original industry research question'
        assert ('DelegateResearchTasksAction' in request['allowed_planning_tools']) is not bounded
        assert ('user explicitly restricted' in request['continuation_policy']) is bounded
        if len(requests) == 1:
            # Deliberately attempt it even in bounded mode: runtime must enforce
            # the user's option rather than trusting model compliance.
            result = _call(request, 'DelegateResearchTasksAction', tasks=[extra], execution_plan=plan)
        else:
            result = _stop(request, ready=True)
            result['action']['tool_calls'][0]['args']['execution_plan'] = plan
            result['action']['tool_calls'][0]['args']['question_coverage'] = [{
                'question_quote': request['research_question'], 'status': 'answered',
                'supporting_task_ids': [unfinished['task_id']],
                'rationale': 'Synthetic coverage to test native handoff; not a financial judgment.'}]
        batch = SpecialistNativeToolBatch.model_validate_json(json.dumps(result['action']))
        result['runtime_receipt'] = RuntimeReceipt(receipt_id='offline-fixture', kind='model',
            actor=request['agent_id'], status='success', request_digest=canonical_sha256(request),
            output_digest=canonical_sha256(batch), elapsed_ms=0.0).model_dump()
        return result

    @contextmanager
    def composition(**kwargs):
        task = kwargs.get('research_task')
        if task:
            workers.append(task['task_id'])
            assert kwargs['research_question'] == 'Original industry research question'
            if has_seed:
                saved = kwargs['dependency_workpapers'][seed['task']['task_id']]
                assert saved['final_submission'] == seed['final_submission']
                assert saved['notebook'] == seed['notebook']
            child = SimpleNamespace(invoke=lambda *a, **k: _worker_result(task, seed))
            yield SimpleNamespace(graph_input=value, graph=child, source_reader=None)
        else:
            yield SimpleNamespace(graph_input=value, source_reader=None)

    def no_provider(*args, **kwargs):
        pytest.fail('Offline wiring must never invoke a specialist provider')
    monkeypatch.setattr(runtime, 'open_specialist_receipted_composition', composition)
    monkeypatch.setattr(runtime.DeepSeekStructuredAgentAdapter, 'from_config', lambda **k:
        SimpleNamespace(lead_research_turn=model, specialist_model_turn=no_provider))
    profile, case = runtime.load_research_runtime_profile(Path(__file__).parents[1])
    phases = runtime.create_research_phase_runnables(root=Path(__file__).parents[1],
        settings={'audit_root': str(tmp_path)}, profile=profile, case=case, run_id='offline-scope', thread_id='offline-thread',
        api_key=SecretStr('offline-not-a-key'), environment={}, public_sink=lambda _: None, private_sink=lambda _: None,
        execution=ExecutionOptions(mode='auto', continuation_scope='original_plan' if bounded else 'original_question'))
    graph = StateGraph(dict).add_node('research', phases['research']).add_edge(START, 'research').add_edge('research', END).compile()
    result = asyncio.run(graph.ainvoke({'question': 'Original industry research question',
        'completed_workpapers': [seed] if has_seed else [], 'unfinished_tasks': [unfinished]}))
    assert workers == [unfinished['task_id']] + ([] if bounded else [extra['task_id']])
    assert result['phase'] == 'research_ready_for_review', (result['stop_reason'], result['tool_results'][-1])
    assert seed == original
    if bounded:
        assert 'continuation_cannot_create_new_tasks' in str(requests[-1]['tool_results'])
    else:
        assert not any('continuation_queued_task_outside_original_scope' in str(r) for r in requests)


@pytest.mark.parametrize('violation', ['duplicate', 'branch', 'capacity'])
def test_adaptive_recovery_keeps_identity_branch_and_capacity_checks(violation):
    seed = _seed()
    task = _task('extra', BRANCHES[1])
    if violation == 'duplicate':
        task['task_id'] = seed['task']['task_id']
    if violation == 'branch':
        task['coverage_obligation_ids'] = ['Q_UNAUTHORIZED']
    errors = {'duplicate': 'task_ids_must_be_new_and_unique', 'branch': 'task_requires_one_disclosed_coverage_obligation',
              'capacity': 'delegated_task_capacity_exceeded'}
    requests = []
    def lead(request):
        requests.append(request)
        if len(requests) == 1:
            return _call(request, 'DelegateResearchTasksAction', tasks=[task])
        assert errors[violation] in str(request['tool_results'])
        return _stop(request, ready=True)
    graph, value = _graph(lead, lambda *_: pytest.fail('invalid new task executed'), seed=seed,
        require_all_branches=False, max_tasks=1 if violation == 'capacity' else 4, max_parallel_tasks=1)
    result = graph.invoke(value.model_dump(mode='json'))
    assert result['task_results'] == []
