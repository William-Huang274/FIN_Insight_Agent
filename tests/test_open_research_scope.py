"""Autonomous scope and real configuration boundaries, with no provider calls."""
import asyncio
from copy import deepcopy
import json

import pytest
from langchain_core.runnables import RunnableLambda
from sec_agent.agent_runtime import research_session_runtime as runtime
from sec_agent.agent_runtime.execution_options import ExecutionOptions
from sec_agent.agent_runtime.lead_research_graph import build_lead_research_graph
from sec_agent.agent_runtime.research_contracts import task_binding_branch
from sec_agent.agent_runtime.specialist_composition import _bind_research_task
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticInput
from test_specialist_graph import _input
from test_lead_research_graph import _task, _call, _stop, _worker_result, _seed, BRANCHES, CATALOG


def current_input():
    body = _input()
    body['task']['case_id'] = 'research:scope-test'
    return SpecialistAgenticInput.model_validate_json(json.dumps(body))


@pytest.mark.parametrize('tags', [[], list(BRANCHES)])
@pytest.mark.parametrize('restore', [False, True])
def test_question_defined_tasks_dispatch_and_handoff_without_catalog_coverage(tags, restore):
    value = current_input()
    seed = _seed()
    seed['task']['case_id'] = value.task.case_id
    original = deepcopy(seed)
    task = _task('cross-company-unlisted')
    task.update(coverage_obligation_ids=tags, objective='解释多家公司签约容量到投产时间的变化如何影响现金回收，而不是按公司列示核查表。')
    seen, ran = [], []
    def model(request):
        seen.append(request)
        assert request['required_branch_ids'] == []
        assert 'unlisted subjects' in request['scope_policy']
        if not request['tasks']:
            return _call(request, 'DelegateResearchTasksAction', tasks=[task])
        return _stop(request, ready=True)
    def worker(assignment, deps, config):
        ran.append(assignment)
        bound = _bind_research_task(value, assignment, {})
        assert bound.task.objective == task['objective']
        assert bound.task_context['assignment']['coverage_obligation_ids'] == tags
        assert bound.task.foundation_digest == value.task.foundation_digest
        assert bound.l0_context == value.l0_context
        result = _worker_result({**assignment, 'coverage_obligation_ids': [bound.task.branch_id]}, seed)
        result['task_context'] = {'assignment': assignment}
        return result
    graph = build_lead_research_graph(expected_input=value, research_question='跨公司经营问题',
        branch_catalog=CATALOG, allowed_branch_ids=BRANCHES, seed_workpapers={},
        model_turn=model, run_child=worker, recovery_tasks=[task] if restore else []).compile()
    result = graph.invoke(value.model_dump(mode='json'))
    assert result['phase'] == 'research_ready_for_review'
    assert len(ran) == 1 and len(seen) == (1 if restore else 2)
    assert seed == original
    assert result['task_results'][0]['agent_state']['notebook']['observations'] == seed['notebook']['observations']


def test_explicit_coverage_uses_semantic_tags_not_transport_branch():
    value = current_input()
    seed = _seed(); seed['task']['case_id'] = value.task.case_id
    task = _task('cross-topic'); task['coverage_obligation_ids'] = list(BRANCHES)
    def model(request):
        assert request['required_branch_ids'] == list(BRANCHES)
        return _call(request, 'DelegateResearchTasksAction', tasks=[task]) if not request['tasks'] else _stop(request, ready=True)
    def worker(task, *_):
        return _worker_result({**task, 'coverage_obligation_ids': [value.task.branch_id]}, seed)
    graph = build_lead_research_graph(expected_input=value, research_question='Explicit multi-topic coverage',
        branch_catalog=CATALOG, allowed_branch_ids=BRANCHES, seed_workpapers={},
        model_turn=model, run_child=worker, require_all_branches=True).compile()
    assert graph.invoke(value.model_dump(mode='json'))['phase'] == 'research_ready_for_review'


@pytest.mark.parametrize('violation', ['capability', 'authority', 'topic', 'dependency'])
def test_open_scope_does_not_grant_permissions_or_accept_broken_dependencies(violation):
    value = current_input(); task = _task(); task['coverage_obligation_ids'] = []
    if violation == 'capability': task['requested_capability_refs'] = ['private:shell']
    if violation == 'authority': task['required_authority_refs'] = ['private:write']
    if violation == 'topic': task['coverage_obligation_ids'] = ['made-up-tag']
    if violation == 'dependency': task['dependency_ids'] = ['missing-task']
    seen = []
    def model(request):
        seen.append(request)
        if len(seen) == 1: return _call(request, 'DelegateResearchTasksAction', tasks=[task])
        assert request['tool_results'][0]['status'] == 'error'
        return _stop(request)
    graph = build_lead_research_graph(expected_input=value, research_question='Question-defined scope',
        branch_catalog=CATALOG, allowed_branch_ids=BRANCHES, seed_workpapers={}, model_turn=model,
        run_child=lambda *_: pytest.fail('Invalid task executed')).compile()
    assert graph.invoke(value.model_dump(mode='json'))['phase'] == 'research_needs_attention'


@pytest.mark.parametrize('mode', ['auto', 'standard'])
def test_default_full_research_is_not_full_catalog(mode):
    assert not ExecutionOptions(mode=mode).require_all_branches
    assert ExecutionOptions(require_all_branches=True).require_all_branches


def test_direct_factory_binds_native_config_before_building_any_phase(monkeypatch):
    built, calls = [], []
    def factory(*, execution, **kwargs):
        built.append(execution)
        def invoke(state):
            calls.append(execution)
            return state
        return {name: RunnableLambda(invoke) for name in ('research', 'writer')}
    monkeypatch.setattr(runtime, '_create_bound_research_phases', factory)
    phases = runtime.create_research_phase_runnables()
    assert not built
    selection = {'mode': 'auto', 'model': 'deepseek-v4-pro', 'continuation_scope': 'original_plan'}
    config = {'configurable': {'finsight_execution': selection}}
    asyncio.run(phases['research'].ainvoke({'question': 'Original question'}, config))
    asyncio.run(phases['writer'].ainvoke({'question': 'Original question'}, config))
    assert built == [ExecutionOptions(**selection)] and calls == built * 2
    with pytest.raises(ValueError, match='changed_within_run'):
        asyncio.run(phases['writer'].ainvoke({}, {'configurable': {'finsight_execution': {'mode': 'standard'}}}))
    assert len(built) == 1


def test_conflicting_factory_and_native_options_fail_before_model_or_data_access(monkeypatch):
    monkeypatch.setattr(runtime, '_create_bound_research_phases', lambda **k: pytest.fail('Constructed under conflicting scope'))
    phases = runtime.create_research_phase_runnables(execution=ExecutionOptions(mode='selected', branch_ids=[BRANCHES[0]]))
    with pytest.raises(ValueError, match='configuration_mismatch'):
        asyncio.run(phases['research'].ainvoke({}, {'configurable': {'finsight_execution': {'mode': 'auto'}}}))


def test_historical_single_tag_identity_is_unchanged():
    task = _task()
    assert task_binding_branch(task, 'other') == BRANCHES[0]
    assert task_binding_branch({'coverage_obligation_ids': []}, 'existing-binding') == 'existing-binding'


@pytest.mark.parametrize('tags', [[], list(BRANCHES)])
def test_open_task_reaches_real_mcp_finance_with_same_identity_and_permissions(monkeypatch, tags):
    from test_current_research_contract import foundation, BRANCH, ASOF
    from test_research_mcp import _build_server
    from sec_agent.research_foundation.mcp_server import FoundationMethodReader
    from sec_agent.agent_runtime.research_mcp_tools import compose_mcp_graph_run, MCPToolLaneAdapter
    from sec_agent.agent_runtime.specialist_composition import _build_graph_input
    current = foundation()
    monkeypatch.setattr(FoundationMethodReader, 'from_default_contract', classmethod(lambda cls: cls(current)))
    graph = compose_mcp_graph_run(current, branch_ids=[BRANCH], research_as_of=ASOF,
        snapshot_id='research-data:test', execution_attempt_id='contract-test')
    base = _build_graph_input(run_id='research-test', run_invocation_id='contract-test', branch_id=BRANCH,
        foundation_binding=graph.foundation_binding, source_route_catalog={'catalog_digest': 'a'*64},
        planner_tool_capabilities={'finance': {'metrics': [{'metric_id': 'revenue', 'observed_tickers': ['MSFT']}]}},
        reviewed_topic_refs_by_branch={}, owner_data_gate_decision_digest='b'*64,
        inventory_snapshot_digest='c'*64, max_model_turns=2, max_tool_actions=4,
        source_read_enabled=True, research_question='Compare companies and investment payback across topics.')
    task = _task(); task.update(coverage_obligation_ids=tags,
        requested_capability_refs=['capability:research:financial-fact-query'])
    bound = _bind_research_task(base, task, {})
    assert bound.task.objective == task['objective']
    assert bound.task.foundation_digest == base.task.foundation_digest
    body = bound.task.model_dump(mode='json')
    body['fact_requests'] = [{'ticker': 'MSFT', 'metric_ids': ['revenue'], 'selection_mode': 'latest_on_or_before'}]
    with MCPToolLaneAdapter(_build_server(), run_binding=graph.mcp_run_binding) as adapter:
        result = adapter.finance_tool({'lane': 'finance', 'task': body})
        assert result['status'] == 'success'
        assert 'MSFT' in json.dumps(result)
        bad = {**body, 'case_id': 'research:another-case'}
        assert adapter.finance_tool({'lane': 'finance', 'task': bad})['status'] == 'tool_failure'
