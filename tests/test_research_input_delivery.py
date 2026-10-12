"""Current catalogs and bounded source handoffs preserve exact research inputs."""
from copy import deepcopy
import json

from langchain_core.messages import HumanMessage

from sec_agent.agent_runtime.research_context_view import compact_current_context, public_operation, working_view
from sec_agent.agent_runtime.specialist_handoff import DependencyReader, selected_source_observations
from sec_agent.agent_runtime.specialist_delegation import ReadDelegatedWorkAction, delegated_artifact_view


def test_initial_catalog_reads_run_bound_method_and_outcome_without_changing_state():
    context = {'allowed_actions': ['read_research_history'], 'task_context': {
        'assignment': {'objective': 'Original question'}, 'overall_assignment': 'Original question',
        'research_working_state': {'findings': ['Current qualified judgment']},
        'stage_methods': {'core_semantics': ['Same units and period'], 'methods': [
            {'method_id': 'finance', 'version': 9, 'summary': 'Finance method', 'content': 'Run-bound custom method '*400}]},
        'delegated_work': [{'subtask_id': 'child', 'objective': 'Explain mechanism', 'phase': 'accepted',
            'outcome': {'execution_status': 'submitted', 'review_status': 'not_assessed',
                'open_gaps': ['Important unresolved issue'], 'author_note': {'summary': 'Answer with conditions',
                'coverage': ['long coverage detail '*300], 'issues': ['material issue']}}}]}}
    saved = deepcopy(context); messages = [HumanMessage(content=json.dumps(context))]
    view = json.loads(working_view(messages)[0].content)['current_context']
    assert view['task_context'] == compact_current_context(context)['task_context'] and context == saved
    assert view['task_context']['research_working_state'] == context['task_context']['research_working_state']
    assert view['task_context']['delegated_work'][0]['outcome']['open_gaps'] == ['Important unresolved issue']
    assert view['task_context']['delegated_work'][0]['author_issues'] == ['material issue']
    for node, expected in [(view['task_context']['stage_methods']['methods'][0], context['task_context']['stage_methods']['methods'][0]),
                           (view['task_context']['delegated_work'][0], context['task_context']['delegated_work'][0])]:
        locator = node.get('details_read', node['read'])['arguments']['tool_call_id']
        assert public_operation(messages, locator)['receipt']['result'] == expected
        assert public_operation([], locator) is None
    assert public_operation(messages, 'runtime:context:/missing') is None


def test_selected_rows_do_not_copy_unrequested_siblings_or_duplicate_receipts():
    a = {'numeric_fact_id': 'A', 'value_decimal': '2', 'period_end': '2026-03-31', 'unit': 'USD'}
    b = {'numeric_fact_id': 'B', 'value_decimal': '3', 'period_end': '2025-03-31', 'unit': 'USD'}
    obs = {'observation_digest': 'original', 'status': 'success', 'references': [{'ref_id': 'A'}, {'ref_id': 'B'}], 'content': [a,b]}
    saved = deepcopy(obs)
    view = selected_source_observations([obs, deepcopy(obs)], {'A'})
    assert len(view) == 1 and view[0]['content'] == [a] and obs == saved
    assert view[0]['references'] == [{'ref_id': 'A'}]
    assert 'observation_digest' not in view[0] and view[0]['original_observation_digest'] == 'original'
    assert selected_source_observations([obs], {'B'})[0]['content'] == [b]


def test_metric_catalog_preserves_all_ids_and_exact_formula_boundary_readback():
    metrics = [{'metric_id': 'gross_margin', 'title': 'Margin', 'unit_family': 'percentage',
        'availability': 'derived_at_query_time', 'formula': 'gross_profit / revenue * 100',
        'interpretation_boundary': 'Same period; ratio does not prove causation', 'observed_tickers': []}]
    context = {'allowed_actions': ['read_research_history'], 'task_context': {'assignment': {}},
        'l0_context': {'capability_summaries': [{'capability_ref': 'capability:research:financial-fact-query',
            'grants_authority': False, 'metrics': metrics}]}}
    compact = compact_current_context(context)['l0_context']['capability_summaries'][0]
    assert compact['grants_authority'] is False
    assert [r[0] for r in compact['metrics']['rows']] == [m['metric_id'] for m in metrics]
    cid = compact['metrics']['rows'][0][-1]
    assert public_operation([HumanMessage(content=json.dumps(context))], cid)['receipt']['result'] == metrics[0]


def test_first_request_keeps_unconsumed_originals_and_current_error():
    source = {'passage_id': 'P', 'passage': 'Complete source with a material condition.'}
    context = {'allowed_actions': ['read_research_history'], 'task_context': {'assignment': {}},
        'progress': {'observations': [{'content': [source]}], 'feedback': [{'code': 'unfinished_read'}]}}
    view = json.loads(working_view([HumanMessage(content=json.dumps(context))])[0].content)
    assert view['current_materials'] == [source]
    assert view['current_context']['progress']['feedback']['initial_feedback'] == context['progress']['feedback']


def test_real_dependency_pages_cover_every_original_and_keep_native_restore_receipts():
    from test_research_session import _new_worker_fixture
    seed = _new_worker_fixture(); saved = deepcopy(seed); task = seed['task']['task_id']
    reader = DependencyReader({task: seed})
    catalog, originals = reader({'task_id': task, 'section': 'sources', 'limit': 12})
    assert not originals
    wanted = [row['source_id'] for row in catalog['sources']]
    request = {'task_id': task, 'section': 'handoff', 'source_ids': wanted, 'limit': 12, 'max_characters': 1000}
    found = []; pages = 0
    while request:
        payload, originals = reader(request); pages += 1
        assert all(o in seed['notebook']['observations'] for o in originals)
        assert payload['source_materials']
        for obs in payload['source_observations']:
            for row in obs['content']:
                assert any(row in o['content'] for o in originals)
        found.extend(row['source_id'] for row in payload['source_materials'])
        request = payload['next_read']['arguments'] if payload.get('next_read') else None
        assert pages <= len(wanted)
    assert set(found) == set(wanted) and len(found) == len(wanted) and pages > 1
    assert seed == saved


def test_delegated_page_next_read_retains_helper_scope_and_budget():
    from test_research_session import _new_worker_fixture
    seed = _new_worker_fixture()
    action = ReadDelegatedWorkAction(action='read_delegated_work', context_digest='a'*64,
        reason_summary='Read originals', subtask_id='helper', section='handoff', limit=12, max_characters=1000)
    payload, original = delegated_artifact_view(seed, action)
    assert original and payload['next_read']['tool'] == 'ReadDelegatedWorkAction'
    assert payload['next_read']['arguments']['subtask_id'] == 'helper'
    assert payload['next_read']['arguments']['max_characters'] == 1000
