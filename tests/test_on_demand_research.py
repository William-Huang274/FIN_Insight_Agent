"""Native deterministic actor/parent transitions, not financial-quality proof."""
import asyncio
from copy import deepcopy
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from mcp import Client

from sec_agent.agent_runtime.research_operation import bind_operation, object_catalog, operation_input
from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from sec_agent.agent_runtime.research_convergence import build_research_convergence_graph
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent
from sec_agent.agent_runtime.case_review_agent import case_mcp_tools
from sec_agent.agent_runtime.on_demand_research import build_on_demand_research_agent
from test_research_convergence import artifact_fixture, independent_review
from test_report_synthesis_agent import NativeFixtureModel
from test_case_review_agent import call
from test_research_mcp import _build_server
from test_conversation_agent import ScriptedTools
from test_case_review_agent import ScriptedNativeChat, review_fixture
from sec_agent.agent_runtime.case_review_agent import build_case_reviewer


def request(action, artifacts, state=None, **kw):
    return {'action': action, 'purpose': 'Answer the current question using these saved objects.',
            'basis': {r['id']: r['digest'] for r in object_catalog(artifacts, state or {})}, **kw}


def report(artifacts):
    claim = artifacts.read_paper('P01')['claims'][0]['claim_id']
    return {'title': 'Native current research fixture', 'narrative_markdown':
        'An explicitly scoped interpretation for deterministic plumbing qualification, not a financial conclusion. '*3 + f'[P01:{claim}]',
        'citations': {}}


async def operation_fixture(action, *, state=None, **kwargs):
    artifacts = artifact_fixture()
    state = state or {}
    operation = request(action, artifacts, state, **kwargs)
    roles, models = [], []
    async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
        tools = await case_mcp_tools(client)
        def make_agent(role, current, **options):
            roles.append(role)
            if role.endswith('verifier'):
                review = {**independent_review(), 'completion': 'complete'}
                replies = [[call('submit_report_review', {'review': review}, 'review')]]
                output_role = 'verifier'
            else:
                output_role = role
                name = 'submit_research_synthesis' if role == 'synthesis' else 'submit_case_report'
                key = 'synthesis' if role == 'synthesis' else 'report'
                value = {k: v for k, v in report(current).items() if k != 'citations'}
                replies = [[call(name, {key: value}, 'submit')]]
            model = NativeFixtureModel(marker='operation-private', replies=replies)
            models.append(model)
            return build_case_output_agent(role=output_role, model=model, tools=tools, artifacts=current,
                limits={'model_calls': 3, 'tool_calls': 8}, on_demand=True,
                review_scope='selected_claims' if operation.get('review_scope') == 'selected' else 'full_report')
        graph = build_research_convergence_graph(artifacts=artifacts, question='What does this evidence imply?',
            feedback={}, research_review_context={}, make_agent=make_agent, operation=operation,
            operation_state=state).compile(checkpointer=InMemorySaver())
        output = await graph.ainvoke({}, {'configurable': {'thread_id': action}, 'recursion_limit': 40})
        return output, roles, models


@pytest.mark.parametrize('action,role', [('synthesize', 'synthesis'), ('compose', 'writer')])
def test_one_operation_returns_without_implicit_review_or_writer(action, role):
    output, roles, _ = asyncio.run(operation_fixture(action))
    assert roles == [role]
    assert output['phase'] == 'research_operation_returned'
    assert output['operation_result']['next_action'] is None
    assert output['operation_result']['status'] == 'submitted'
    assert 'report_review' not in output and 'synthesis_review' not in output


def test_selected_review_never_becomes_full_report_acceptance():
    artifacts = artifact_fixture()
    state = {'report': report(artifacts)}
    output, roles, _ = asyncio.run(operation_fixture('review_report', state=state,
        review_scope='selected', quotes=['An explicitly scoped interpretation for deterministic plumbing qualification, not a financial conclusion. '*3]))
    assert roles == ['report_verifier']
    result = output['operation_result']
    assert result['output']['full_report_acceptance'] is False
    assert result['locations'][0]['start'] == 0
    assert result['basis']['report'] == canonical_sha256(state['report'])
    assert output['report'] == state['report']


def test_stale_version_rejected_before_any_agent_and_old_requirements_exit():
    artifacts = artifact_fixture()
    old = {'report': report(artifacts)}
    op = request('review_report', artifacts, old)
    current = deepcopy(old)
    current['report']['narrative_markdown'] += ' Changed.'
    with pytest.raises(ValueError, match='version_changed'):
        bind_operation(op, artifacts, current)
    bound = bind_operation(request('compose', artifacts, current), artifacts, current)
    seed = operation_input(bound, {**current, 'research_handoff': {'execution_plan': 'FORCE ALL OLD STAGES'},
        'report_review': {'summary': 'OLD UNBOUND VERDICT'}, 'pending_feedback': {'P99': 'obsolete'}})
    assert 'FORCE ALL' not in str(seed) and 'OLD UNBOUND' not in str(seed)
    assert seed['report'] == current['report']


def test_parent_can_deliver_workpaper_without_report_or_review():
    artifacts = artifact_fixture()
    row = object_catalog(artifacts, {})[0]
    model = ScriptedTools(responses=[AIMessage(content='', tool_calls=[call('deliver_research_result',
        {'object_id': row['id'], 'digest': row['digest']}, 'deliver')])])
    async def forbidden(*args):
        pytest.fail('A workpaper delivery must not call report stages')
    graph = build_on_demand_research_agent(model=model, grants=[], artifacts=lambda s: artifacts,
        operation_runner=RunnableLambda(forbidden), permission_mode='request_standard',
        checkpointer=InMemorySaver(), delivery_intent='workpaper')
    result = asyncio.run(graph.ainvoke({'messages': [HumanMessage(content='Return this workpaper')], 'question': 'Current question'},
        {'configurable': {'thread_id': 'workpaper', 'run_id': 'one'}}))
    assert result['delivery']['artifact_kind'] == 'workpaper'
    assert result['delivery']['review_status'] == 'not_assessed_in_this_record'
    assert not result.get('report')


def test_parent_selects_one_operation_then_answers_without_fixed_successors():
    artifacts = artifact_fixture()
    op = request('synthesize', artifacts)
    bound = bind_operation(op, artifacts, {})
    model = ScriptedTools(responses=[AIMessage(content='', tool_calls=[call('request_research_operation', {'request': op}, 'choose')]),
                                   AIMessage(content='Here is what these observations mean.')])
    calls = []
    async def runner(state):
        calls.append(state['research_operation']['action'])
        value = report(artifacts)
        return {'synthesis': value, 'operation_result': {**bound, 'output': value, 'status': 'submitted'}}
    graph = build_on_demand_research_agent(model=model, grants=[], artifacts=lambda s: artifacts,
        operation_runner=RunnableLambda(runner), permission_mode='request_standard', checkpointer=InMemorySaver())
    result = asyncio.run(graph.ainvoke({'messages': [HumanMessage(content='Interpret these findings')], 'question': 'Current question'},
        {'configurable': {'thread_id': 'choose', 'run_id': 'one'}}))
    assert calls == ['synthesize'] and len(result['operation_records']) == 1
    assert result['messages'][-1].content == 'Here is what these observations mean.'
    assert 'report' not in result


@pytest.mark.parametrize('reviewer', ['counter', 'verifier'])
def test_one_workpaper_check_returns_without_full_case_assessments(reviewer):
    async def exercise():
        artifacts = artifact_fixture()
        op = request('review_workpaper', artifacts, paper_id='P01', reviewer=reviewer)
        value = {**review_fixture(artifacts), 'completion': 'complete'}
        value['assessments'] = value['assessments'][:1]
        async with Client(_build_server(case_artifacts=artifacts)) as client:
            tools = await case_mcp_tools(client)
            roles = []
            def factory(role, current, **kw):
                roles.append(role)
                return build_case_reviewer(role=role, artifacts=current, tools=tools, operation_paper_id=kw['paper_id'],
                    model=ScriptedNativeChat(marker='optional-review', replies=[
                        [call('read_research_artifact', {'paper_id': 'P01', 'section': 'workpaper'}, 'read')],
                        [call('submit_case_review', {'review': value}, 'submit')]]))
            graph = build_research_convergence_graph(artifacts=artifacts, question='Check this paper',
                feedback={}, research_review_context={}, make_agent=factory, operation=op).compile(checkpointer=InMemorySaver())
            result = await graph.ainvoke({}, {'configurable': {'thread_id': reviewer}})
        assert roles == [reviewer]
        assert result['workpaper_review']['review_scope']['whole_case_acceptance'] is False
        assert len(result['workpaper_review']['assessments']) == 1
        assert result['operation_result']['next_action'] is None
    asyncio.run(exercise())


def test_original_author_revision_returns_without_implied_confirmation():
    async def exercise():
        artifacts = artifact_fixture()
        seen = []
        async def author(pid, state, config):
            seen.append(pid)
            paper = artifacts.read_paper(pid)
            paper['thesis'] += ' Revised synthetic interpretation.'
            return {'status': 'revision_submitted', 'workpaper': paper, 'finding_responses': [
                {'finding_id': 'F1', 'disposition': 'corrected', 'explanation': 'Synthetic local modification.'}]}
        def forbidden(*a, **kw):
            pytest.fail('No implicit reviewer/writer')
        op = request('revise_workpaper', artifacts, paper_id='P01', findings=[{
            'finding_id': 'F1', 'diagnosis': 'Reconsider thesis', 'requested_change': 'Reassess the current wording'}])
        graph = build_research_convergence_graph(artifacts=artifacts, question='Revise', feedback={},
            research_review_context={}, make_agent=forbidden, run_author=author, operation=op).compile()
        result = await graph.ainvoke({})
        assert seen == ['P01'] and result['operation_result']['status'] == 'submitted'
        assert result['revisions']['P01']['runtime_changes']['locations']
        assert not result.get('workpaper_confirmation') and not result.get('report')
    asyncio.run(exercise())


def test_review_is_not_reused_after_an_available_dependency_changes():
    artifacts = artifact_fixture()
    state = {'report': report(artifacts)}
    req = request('review_report', artifacts, state)
    req['basis'] = {'report': canonical_sha256(state['report'])}
    before = bind_operation(req, artifacts, state)
    state['operation_records'] = [{**before, 'output': independent_review(), 'status': 'submitted'}]
    paper = artifacts.read_paper('P01')
    paper['thesis'] += ' New evidence changed this judgment.'
    state['revisions'] = {'P01': {'status': 'revision_submitted', 'workpaper': paper, 'finding_responses': []}}
    after = bind_operation(req, artifacts, state)
    assert after['operation_digest'] != before['operation_digest']
    assert 'report_review' not in operation_input(after, state)


@pytest.mark.parametrize('which', ['model', 'tool'])
def test_parent_limits_do_not_reset_when_operation_returns(which):
    artifacts = artifact_fixture()
    op = request('synthesize', artifacts)
    bound = bind_operation(op, artifacts, {})
    model = ScriptedTools(responses=[AIMessage(content='', tool_calls=[call('request_research_operation', {'request': op}, 'one')]),
                                   AIMessage(content='Must not be called beyond this bound')])
    async def runner(state):
        return {'operation_result': {**bound, 'output': {}, 'status': 'submitted'}}
    graph = build_on_demand_research_agent(model=model, grants=[], artifacts=lambda s: artifacts,
        operation_runner=RunnableLambda(runner), permission_mode='request_standard', checkpointer=InMemorySaver(),
        model_calls=1 if which == 'model' else 8, tool_calls=1 if which == 'tool' else 12)
    with pytest.raises(ValueError, match='on_demand_parent_'+which+'_limit_reached'):
        asyncio.run(graph.ainvoke({'messages': [HumanMessage(content='Do one operation')], 'question': 'Question'},
            {'configurable': {'thread_id': which, 'run_id': 'bounded'}}))


def test_general_answer_needs_no_case_or_report_initialization():
    def forbidden(*args):
        pytest.fail('An ordinary answer must not initialize research artifacts')
    graph = build_on_demand_research_agent(model=ScriptedTools(responses=[AIMessage(content='A short useful answer.')]),
        grants=[], artifacts=forbidden, operation_runner=RunnableLambda(forbidden), permission_mode='request_standard',
        checkpointer=InMemorySaver())
    result = asyncio.run(graph.ainvoke({'messages': [HumanMessage(content='Explain this concept')]},
        {'configurable': {'thread_id': 'answer', 'run_id': 'answer'}}))
    assert result['messages'][-1].content == 'A short useful answer.'
    assert not result.get('case_papers') and not result.get('report')


def test_wrong_version_feedback_can_be_corrected_without_recreating_work():
    artifacts = artifact_fixture()
    row = object_catalog(artifacts, {})[0]
    model = ScriptedTools(responses=[AIMessage(content='', tool_calls=[call('deliver_research_result',
        {'object_id': row['id'], 'digest': '0'*64}, 'wrong')]), AIMessage(content='', tool_calls=[call('deliver_research_result',
        {'object_id': row['id'], 'digest': row['digest']}, 'correct')])])
    async def forbidden(*a):
        pytest.fail('Do not regenerate a workpaper to correct its version reference')
    graph = build_on_demand_research_agent(model=model, grants=[], artifacts=lambda s: artifacts,
        operation_runner=RunnableLambda(forbidden), permission_mode='request_standard', checkpointer=InMemorySaver(),
        delivery_intent='workpaper')
    result = asyncio.run(graph.ainvoke({'messages': [HumanMessage(content='Deliver this workpaper')]},
        {'configurable': {'thread_id': 'correctable', 'run_id': 'one'}}))
    assert result['delivery']['artifact_digest'] == row['digest']
    assert result['parent_calls'] == 2


def test_parent_keeps_native_external_approval_and_resumes_without_repeating_tool():
    from langchain_core.tools import tool
    from langgraph.types import Command
    from sec_agent.agent_runtime.conversation_agent import GrantedTool
    writes = []
    @tool
    def external_change():
        """Synthetic external change; requires actual approval."""
        writes.append('changed')
        return 'changed'
    model = ScriptedTools(responses=[AIMessage(content='', tool_calls=[call('external_change', {}, 'external')]),
                                   AIMessage(content='The requested change is complete.')])
    graph = build_on_demand_research_agent(model=model, grants=[GrantedTool(external_change, 'external_change', 'One test object')],
        artifacts=lambda s: artifact_fixture(), operation_runner=RunnableLambda(lambda s: pytest.fail('unexpected operation')),
        permission_mode='request_standard', checkpointer=InMemorySaver())
    async def exercise():
        config = {'configurable': {'thread_id': 'approval', 'run_id': 'one'}}
        paused = await graph.ainvoke({'messages': [HumanMessage(content='Make this external change')]}, config)
        assert paused['__interrupt__'] and not writes
        result = await graph.ainvoke(Command(resume={'decisions': [{'type': 'approve'}]}), config)
        assert writes == ['changed']
        assert result['messages'][-1].content == 'The requested change is complete.'
    asyncio.run(exercise())


def test_composition_from_saved_sources_does_not_require_fake_expert_papers():
    from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
    async def exercise():
        ref = 'NUMFACT::fixture'
        source = {'numeric_fact_id': ref, 'result_state': 'numeric_fact', 'ticker': 'FIX',
            'metric_id': 'net_income', 'value_decimal': '12', 'unit': 'USD', 'period_end': '2025-12-31',
            'numeric_fact_authority': True}
        artifacts = CaseArtifacts.from_observed_sources({ref: source}, case_id='fixture', research_as_of='2026-01-01')
        op = request('compose', artifacts)
        assert set(op['basis']) == {'observed_sources'}
        value = {'title': 'Source-only composition fixture', 'narrative_markdown':
            'This is a synthetic plumbing example, not a financial conclusion. '*5 + f'Net income 12 USD [{ref}].'}
        def factory(role, current, **kw):
            assert role == 'writer' and current.catalog()['papers'] == []
            return build_case_output_agent(role='writer', artifacts=current, tools=[], on_demand=True,
                limits={'model_calls': 3, 'tool_calls': 4}, model=NativeFixtureModel(marker='source-only', replies=[
                    [call('read_current_source', {'source_id': ref}, 'read')],
                    [call('submit_case_report', {'report': value}, 'write')]]))
        graph = build_research_convergence_graph(artifacts=artifacts, question='Write a small report from these observations',
            feedback={}, research_review_context={}, make_agent=factory, operation=op).compile(checkpointer=InMemorySaver())
        result = await graph.ainvoke({}, {'configurable': {'thread_id': 'source-only'}})
        assert result['report']['citations'][ref]
        assert not result.get('report_review') and artifacts.catalog()['papers'] == []
    asyncio.run(exercise())


def test_source_version_excludes_transport_but_preserves_content_and_authority():
    from sec_agent.agent_runtime.research_operation import source_collection_digest
    source = {'calculation_id': 'CALC::fixture', 'value_decimal': '12', 'result_unit': 'USD',
              'numeric_fact_authority': False, 'operands': {'x': {'literal': '6'}}, 'expression': 'x*2'}
    wrapped = {**source, 'mcp_receipt_chain': [{'call_id': 'transport'}], 'source_tool_lane_receipt_id': 'receipt',
               'cell_binding_used': False, 'fact_id': source['calculation_id'], 'operand_source_aliases': {}}
    expected = source_collection_digest({'S1': source})
    assert source_collection_digest({'S1': wrapped}) == expected
    for key, value in [('value_decimal', '13'), ('numeric_fact_authority', True), ('result_unit', 'CNY'),
                       ('cell_binding_used', True), ('fact_id', 'different'), ('operand_source_aliases', {'x': 'S9'})]:
        assert source_collection_digest({'S1': {**wrapped, key: value}}) != expected
    assert wrapped['mcp_receipt_chain']  # Journal objects were not mutated.


def test_freeform_note_delivery_reuses_bd_handoff_without_native_case(tmp_path):
    from sec_agent.agent_runtime.working_memory import WorkingMemory
    memory = WorkingMemory(tmp_path/'notes.sqlite', owner='owner', workspace='root-task', actor='lead')
    body = 'This is free-form research, not a typed financial claim record. '*250
    saved = memory.save('Current working paper', body)
    model = ScriptedTools(responses=[AIMessage(content='', tool_calls=[call('deliver_working_note',
        {'note_id': saved['note_id'], 'version': saved['version']}, 'note')])])
    def forbidden(*args):
        pytest.fail('Free-form workpaper delivery must not initialize case/report artifacts')
    graph = build_on_demand_research_agent(model=model, grants=[], artifacts=forbidden,
        operation_runner=RunnableLambda(forbidden), permission_mode='request_standard', checkpointer=InMemorySaver(),
        delivery_intent='workpaper', working_memory=memory)
    result = asyncio.run(graph.ainvoke({'messages': [HumanMessage(content='Deliver the saved working paper')]},
        {'configurable': {'thread_id': 'note', 'run_id': 'one'}}))
    assert result['delivery']['artifact_digest'] == canonical_sha256(body)
    assert result['task_outcome']['artifact_kind'] == 'workpaper'
    assert result['task_outcome']['execution_status'] == 'submitted'
    assert 'report' not in result


def test_plain_claim_of_report_completion_is_not_a_submitted_artifact():
    artifacts = artifact_fixture()
    graph = build_on_demand_research_agent(model=ScriptedTools(responses=[AIMessage(content='The report is done.')]),
        grants=[], artifacts=lambda s: artifacts, operation_runner=RunnableLambda(lambda s: {}),
        permission_mode='request_standard', checkpointer=InMemorySaver(), delivery_intent='report')
    result = asyncio.run(graph.ainvoke({'messages': [HumanMessage(content='Deliver a report')]},
        {'configurable': {'thread_id': 'not-done', 'run_id': 'one'}}))
    assert result['task_outcome']['execution_status'] == 'incomplete'
    assert result['task_outcome']['artifact_status'] == 'none'


def test_requested_report_check_cannot_use_partial_scope_as_full_acceptance():
    artifacts = artifact_fixture()
    state = {'report': report(artifacts)}
    row = next(r for r in object_catalog(artifacts, state) if r['id'] == 'report')
    state['operation_records'] = [{'action': 'review_report', 'operation_digest': 'scoped-check',
        'basis': {'report': row['digest']}, 'review_scope': 'selected', 'status': 'submitted',
        'output': {'completion': 'complete', 'findings': [], 'unresolved_data_requests': []}}]
    model = ScriptedTools(responses=[AIMessage(content='', tool_calls=[call('deliver_research_result',
        {'object_id': 'report', 'digest': row['digest']}, 'deliver')]), AIMessage(content='The requested whole-report check is still pending.')])
    graph = build_on_demand_research_agent(model=model, grants=[], artifacts=lambda s: artifacts,
        operation_runner=RunnableLambda(lambda s: pytest.fail('No implicit review')),
        permission_mode='request_standard', checkpointer=InMemorySaver(), delivery_intent='report', required_report_review=True)
    result = asyncio.run(graph.ainvoke({**state, 'messages': [HumanMessage(content='Deliver only after the specified check')]},
        {'configurable': {'thread_id': 'partial', 'run_id': 'one'}}))
    assert result['task_outcome']['execution_status'] == 'incomplete' and not result.get('delivery')


def test_saved_operation_survives_parent_stop_and_is_not_reexecuted():
    async def exercise():
        artifacts = artifact_fixture()
        op = request('synthesize', artifacts)
        bound = bind_operation(op, artifacts, {})
        calls = []
        async def runner(state):
            calls.append('executed')
            return {'synthesis': report(artifacts), 'operation_result': {**bound, 'output': report(artifacts), 'status': 'submitted'}}
        model = ScriptedTools(responses=[AIMessage(content='', tool_calls=[call('request_research_operation', {'request': op}, 'choose')]),
            AIMessage(content='Continue from the saved synthesis.')])
        graph = build_on_demand_research_agent(model=model, grants=[], artifacts=lambda s: artifacts,
            operation_runner=RunnableLambda(runner), permission_mode='request_standard', checkpointer=InMemorySaver(), model_calls=1)
        config = {'configurable': {'thread_id': 'resume', 'run_id': 'first'}}
        with pytest.raises(ValueError, match='on_demand_parent_model_limit_reached'):
            await graph.ainvoke({'messages': [HumanMessage(content='Interpret this')], 'question': 'Interpret'}, config)
        saved = await graph.aget_state(config)
        assert len(saved.values['operation_records']) == 1 and saved.values['synthesis']
        result = await graph.ainvoke(None, {'configurable': {'thread_id': 'resume', 'run_id': 'second'}})
        assert calls == ['executed'] and result['task_outcome']['artifact_kind'] == 'answer'
    asyncio.run(exercise())


def test_native_parent_can_choose_synthesis_composition_check_and_delivery_in_sequence():
    from langchain_core.outputs import ChatResult, ChatGeneration
    artifacts = artifact_fixture()
    roles = []
    class Parent(ScriptedTools):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            notices = [m for m in messages if isinstance(m, HumanMessage) and str(m.content).startswith('Runtime operation receipt')]
            rows = json.loads(notices[-1].content.split(': ', 1)[1])['objects'] if notices else object_catalog(artifacts, {})
            if len(notices) == 3:
                row = next(r for r in rows if r['id'] == 'report')
                action = call('deliver_research_result', {'object_id': 'report', 'digest': row['digest']}, 'delivery')
            else:
                name = ['synthesize', 'compose', 'review_report'][len(notices)]
                action = call('request_research_operation', {'request': {'action': name,
                    'purpose': 'Synthetic chosen operation '+name, 'basis': {r['id']: r['digest'] for r in rows}}}, name)
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content='', tool_calls=[action]))])
    async def exercise():
        async with Client(_build_server(case_artifacts=artifacts)) as client:
            tools = await case_mcp_tools(client)
            def factory(role, current, **kwargs):
                roles.append(role)
                if role == 'report_verifier':
                    output_role = 'verifier'
                    reply = call('submit_report_review', {'review': {**independent_review(), 'completion': 'complete'}}, role)
                else:
                    output_role = role
                    key = 'synthesis' if role == 'synthesis' else 'report'
                    reply = call('submit_research_synthesis' if role == 'synthesis' else 'submit_case_report',
                        {key: {k: v for k, v in report(current).items() if k != 'citations'}}, role)
                return build_case_output_agent(role=output_role, artifacts=current, tools=tools, on_demand=True,
                    model=NativeFixtureModel(marker=role, replies=[[reply]]), limits={'model_calls': 3, 'tool_calls': 8})
            async def operate(state, config):
                graph = build_research_convergence_graph(artifacts=artifacts, question='Original question',
                    feedback={}, research_review_context={}, make_agent=factory,
                    operation=state['research_operation'], operation_state=state).compile()
                return await graph.ainvoke({}, config)
            graph = build_on_demand_research_agent(model=Parent(responses=[]), grants=[], artifacts=lambda s: artifacts,
                operation_runner=RunnableLambda(operate), permission_mode='request_standard', checkpointer=InMemorySaver(),
                delivery_intent='report', required_report_review=True)
            result = await graph.ainvoke({'messages': [HumanMessage(content='Make and check a report')]},
                {'configurable': {'thread_id': 'sequence', 'run_id': 'one'}, 'recursion_limit': 100})
            assert roles == ['synthesis', 'writer', 'report_verifier']
            assert len(result['operation_records']) == 3
            assert result['task_outcome']['execution_status'] == 'submitted'
            assert result['task_outcome']['artifact_kind'] == 'report'
    asyncio.run(exercise())
