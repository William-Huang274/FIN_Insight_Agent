import pytest
import json
from contextlib import asynccontextmanager

from uuid import uuid4

@pytest.fixture
def anyio_backend():
    return 'asyncio'


from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from sec_agent.agent_runtime.conversation_agent import GrantedTool
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.harness_acp_session import admitted_acp_session


def test_recovered_calculator_rechecks_original_without_rewriting_history():
    from copy import deepcopy
    from langchain_core.messages import AIMessage
    from sec_agent.agent_runtime.harness_business_tools import restored_batch_feedback
    source = {'passage_id': 'PASSAGE::test', 'passage': '占比为6.1%，去年为5.4%',
              'result_state': 'source_bound_passage', 'writer_citable': True,
              'numeric_fact_authority': False}
    args = {'request': {'expression': 'a-b', 'operands': {
        'a': {'source_id': source['passage_id'], 'quote': source['passage'], 'literal': '6.1'},
        'b': {'source_id': source['passage_id'], 'quote': source['passage'], 'literal': '5.4'}},
        'result_unit': '百分点', 'rationale': 'Compare the reported shares.'}}
    messages = [ToolMessage(content='read', tool_call_id='read', name='read_source_document',
                           artifact={'operation': 'read', 'items': [source]}),
                AIMessage(content='', tool_calls=[{'id': 'calc', 'name': 'calculate_research_metric', 'args': args}]),
                ToolMessage(content='numeric_literal_not_in_exact_source_quote: operand=a',
                            tool_call_id='calc', name='calculate_research_metric', status='error')]
    before = deepcopy(messages)
    result = restored_batch_feedback(messages, {'calc'})
    assert messages == before
    assert result['kind'] == 'rechecked_tool_rejections' and not result['failures']
    checked = result['revalidated'][0]
    assert checked['current_status'] == 'original_proposal_revalidated_not_saved'
    assert checked['check']['value_decimal'] == '0.7'
    assert not checked['check']['financial_semantics_verified']
    assert checked['retry']['arguments'] == args
    assert checked['historical_failure']['status'] == 'error'
    # A later malformed proposal is still rejected; do not copy a prior quote.
    messages[1].tool_calls[0]['args']['request']['operands']['a'].pop('quote')
    failed = restored_batch_feedback(messages, {'calc'})
    assert failed['kind'] == 'saved_tool_rejections' and failed['failures']
    assert 'revalidated' not in failed


@pytest.mark.anyio
async def test_unobserved_source_feedback_survives_pending_read_recovery(tmp_path):
    from langchain_core.messages import AIMessage
    from sec_agent.agent_runtime.organization_work_session import observed_source_tool, select_observed_sources
    from types import SimpleNamespace
    requested = 'PASSAGE::ORGSECTION::example:chunk-example::1'
    observed = 'PASSAGE::ORGSECTION::example:chunk-example::digest'
    source = {'passage_id': observed, 'text': 'unchanged original'}
    accesses = []
    def reader(state, **kwargs):
        return SimpleNamespace(source_snapshot=lambda: select_observed_sources(state, **kwargs))
    grants = [observed_source_tool(reader, lambda: accesses.append('checked'))]
    grants += [g for g in conversation_tools(thread_id='t') if g.tool.name in {'browse_context', 'read_saved_result'}]
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='t', check=lambda: None)
        prior = ToolMessage(content='original', name='read_source_document', tool_call_id='prior',
            artifact={'source_items': {observed: source}})
        await bridge.initialize({'messages': [prior]})
        response = await bridge.call_tool(None, SimpleNamespace(name='read_research_source',
            arguments={'source_id': requested, 'max_characters': 6000}))
        assert response.is_error
        feedback = json.loads(response.content[0].text)['result']
        assert feedback['requested_source_id'] == requested
        assert feedback['readback'] == {'tool': 'browse_context', 'arguments': {'region': 'sources'}}
        bridge.model_access()  # ordinary selection feedback does not poison dispatch
        assert (await bridge.state())['messages'][0].artifact == prior.artifact
        catalog = await bridge.execute('browse_context', {'region': 'sources'})
        assert 'prior' in catalog.content
        # Reproduce a legacy interrupted read; recovery preserves its exact args
        # and returns typed feedback rather than requiring a successful read.
        await bridge._checkpoint_call(bridge.graph.aupdate_state, bridge.config, {'messages': [
            AIMessage(content='', tool_calls=[{'name': 'read_research_source', 'args': {'source_id': requested},
                'id': 'pending', 'type': 'tool_call'}])]}, as_node='__start__')
        restored = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='t', check=lambda: None)
        receipt = await restored.initialize({}, recovering=True)
        assert receipt['kind'] == 'recovered_read_feedback'
        assert receipt['status'] == 'error'
        assert receipt['feedback']['result']['requested_source_id'] == requested
        restored.model_access()


@pytest.mark.anyio
async def test_business_graph_inside_parent_task_keeps_its_own_checkpoint(tmp_path):
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import InMemorySaver
    from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessState
    @tool
    def read_existing():
        """Read the saved research fixture."""
        return 'existing evidence'
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=[GrantedTool(read_existing, 'read', 'fixture')],
            checkpointer=saver, thread_id='fixture', check=lambda: None)
        await bridge.initialize({'question': 'original', 'messages': []})
        async def work(state):
            receipt = await bridge.execute('read_existing', {})
            assert receipt.content == 'existing evidence'
            return {'messages': [receipt]}
        g = StateGraph(HarnessBusinessState)
        g.add_node('work', work); g.add_edge(START, 'work'); g.add_edge('work', END)
        parent = g.compile(checkpointer=InMemorySaver())
        await parent.ainvoke({'question': 'outer', 'messages': []}, {'configurable': {'thread_id': 'fixture'}})
        business = await bridge.state()
        assert business['question'] == 'original'
        assert len([m for m in business['messages'] if isinstance(m, ToolMessage)]) == 1


@pytest.mark.anyio
async def test_real_calculator_preserves_sources_across_bridge_restart(tmp_path):
    source = {'numeric_fact_id': 'NUMFACT::test', 'result_state': 'numeric_fact',
              'numeric_fact_authority': True, 'value_decimal': '120', 'unit': 'USD million',
              'ticker': 'TEST', 'period_start': '2025-01-01', 'period_end': '2025-12-31'}
    @tool(response_format='content_and_artifact')
    def query_financial_data():
        """Read the synthetic source."""
        body = {'authority_state': 's2_numeric_fact_query_result', 'results': [{'status': 'resolved', 'facts': [source]}]}
        return json.dumps(body), body
    grants = [GrantedTool(query_financial_data, 'read', 'fixture source')]
    grants += [g for g in conversation_tools(thread_id='fixture')
               if g.tool.name in {'calculate_research_metric', 'read_saved_result', 'browse_context'}]
    params = {'request': {'expression': 'revenue / 2',
              'operands': {'revenue': {'source_id': 'NUMFACT::test'}},
              'result_unit': 'USD million', 'rationale': 'fixture arithmetic'}}
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        first = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='fixture', check=lambda: None)
        await first.initialize({'question': 'Original question', 'messages': []})
        receipt = await first.execute('query_financial_data', {})
        assert receipt.status == 'success'
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        second = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='fixture', check=lambda: None)
        await second.initialize({'question': 'do not replace', 'messages': []})
        assert (await second.state())['question'] == 'Original question'
        from sec_agent.agent_runtime.source_references import reference_handle
        params['request']['operands']['revenue']['source_id'] = reference_handle('NUMFACT::test')
        computed = await second.execute('calculate_research_metric', params)
        assert computed.status == 'success', computed.content
        assert computed.artifact['value_decimal'] == '60'
        saved = await second.state()
        proposal = saved['messages'][-2]
        assert proposal.tool_calls[0]['args']['request']['operands']['revenue']['source_id'] == 'NUMFACT::test'
        assert proposal.additional_kwargs['original_tool_arguments']['request']['operands']['revenue']['source_id'] == reference_handle('NUMFACT::test')
        read = await second.execute('read_saved_result', {'tool_call_id': receipt.tool_call_id})
        assert '120' in read.content
        assert len([m for m in (await second.state())['messages'] if isinstance(m, ToolMessage)]) == 3
        catalog = await second.execute('browse_context', {'region': 'numbers'})
        assert receipt.tool_call_id in catalog.content
        schema = await second.list_tools(None, None)
        assert all('runtime' not in t.input_schema.get('properties', {}) for t in schema.tools)


@pytest.mark.anyio
async def test_tool_failure_stops_following_calls_but_selection_feedback_does_not(tmp_path):
    @tool
    def broken():
        """Synthetic storage failure."""
        raise OSError('storage unavailable')
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=[GrantedTool(broken, 'read', 'test')], checkpointer=saver,
                                      thread_id='fixture', check=lambda: None)
        await bridge.initialize({'question': 'q', 'messages': []})
        with pytest.raises(OSError):
            await bridge.execute('broken', {})
        with pytest.raises(RuntimeError, match='stopped'):
            await bridge.list_tools(None, None)


@pytest.mark.anyio
async def test_interrupted_read_resumes_exact_pending_call_preserving_successes(tmp_path):
    calls = []
    broken = True
    @tool
    def read_research_source(key: str):
        """Read the original source."""
        calls.append(key)
        if key == 'second' and broken:
            raise OSError('storage unavailable')
        return 'original:' + key
    grants = [GrantedTool(read_research_source, 'read', 'fixture')]
    grants += [g for g in conversation_tools(thread_id='t') if g.tool.name == 'read_saved_result']
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        first = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='t', check=lambda: None)
        await first.initialize({'messages': [], 'question': 'original'})
        saved = await first.execute('read_research_source', {'key': 'first'})
        with pytest.raises(OSError):
            await first.execute('read_research_source', {'key': 'second'})
        second = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='t', check=lambda: None)
        with pytest.raises(RuntimeError, match='reconcile_before_resume'):
            await second.initialize({})
        broken = False
        recovery = await second.initialize({}, recovering=True)
        assert recovery['tool'] == 'read_research_source'
        messages = (await second.state())['messages']
        assert saved in messages
        assert messages[-1].content == 'original:second'
        assert messages[-1].tool_call_id == recovery['receipt_id']
        assert await second.initialize({}, recovering=True) is None
        assert calls == ['first', 'second', 'second']
        reread = await second.execute('read_saved_result', {'tool_call_id': recovery['receipt_id']})
        assert reread.status == 'success' and 'original:second' in reread.content
        assert calls == ['first', 'second', 'second']
        history = [s async for s in saver.alist(second.config)]
        assert any(any(w[1] == '__error__' for w in (s.pending_writes or [])) for s in history)


@pytest.mark.anyio
async def test_client_timeout_cannot_dispatch_while_server_read_is_unresolved(tmp_path):
    import asyncio
    started, release = asyncio.Event(), asyncio.Event()
    @tool
    async def slow_read():
        """Simulate an MCP server read outliving its client timeout."""
        started.set()
        await release.wait()
        return 'late original result'
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=[GrantedTool(slow_read, 'read', 'fixture')],
            checkpointer=saver, thread_id='t', check=lambda: None)
        await bridge.initialize({'messages': []})
        task = asyncio.create_task(bridge.execute('slow_read', {}))
        await started.wait()
        with pytest.raises(RuntimeError, match='effect_unresolved'):
            bridge.model_access()
        release.set()
        with pytest.raises(RuntimeError, match='stopped'):
            await task
        with pytest.raises(RuntimeError, match='stopped'):
            bridge.model_access()
        restored = HarnessBusinessTools(grants=[GrantedTool(slow_read, 'read', 'fixture')],
            checkpointer=saver, thread_id='t', check=lambda: None)
        await restored.initialize({}, recovering=True)
        assert (await restored.state())['messages'][-1].content == 'late original result'


@pytest.mark.anyio
async def test_recovery_does_not_replay_unknown_write_effect(tmp_path):
    writes = []
    @tool
    def save_note():
        """Save a note and simulate an unknown acknowledgement."""
        writes.append('saved')
        raise OSError('acknowledgement missing')
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        grants = [GrantedTool(save_note, 'working_note_write', 'fixture')]
        first = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='t', check=lambda: None)
        await first.initialize({'messages': []})
        with pytest.raises(OSError):
            await first.execute('save_note', {})
        second = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='t', check=lambda: None)
        with pytest.raises(RuntimeError, match='reconcile_before_resume'):
            await second.initialize({}, recovering=True)
        assert writes == ['saved']


@pytest.mark.anyio
async def test_session_binding_resume_completed_reuse_and_private_events(tmp_path):
    from acp.schema import InitializeResponse, NewSessionResponse, PromptResponse, AgentMessageChunk, TextContentBlock
    actions = []
    @asynccontextmanager
    async def spawn(client, *args, **kwargs):
        class Connection:
            async def initialize(self, **kw):
                return InitializeResponse(protocolVersion=1, agentCapabilities={'loadSession': True})
            async def new_session(self, **kw):
                actions.append('new')
                return NewSessionResponse(sessionId='saved-acp')
            async def load_session(self, **kw):
                actions.append(('load', kw['session_id']))
            async def prompt(self, **kw):
                actions.append('prompt')
                await client.session_update('saved-acp', AgentMessageChunk(sessionUpdate='agent_message_chunk',
                    content=TextContentBlock(type='text', text='Public answer')))
                return PromptResponse(stopReason='end_turn')
        yield Connection(), None
    common = dict(binary='fixture', arguments=[], environment={}, directory=tmp_path,
                  binding={'task': 'verified-java-task'}, authority=lambda: None, stop=lambda: None,
                  mcp_servers=[], spawn=spawn)
    run = str(uuid4())
    async with admitted_acp_session(**common, run_id=run) as session:
        assert (await session.prompt('original question'))['text'] == 'Public answer'
        assert (await session.prompt('original question'))['text'] == 'Public answer'
        with pytest.raises(ValueError, match='identity_changed'):
            await session.prompt('different instruction under same run')
    async with admitted_acp_session(**common, run_id=str(uuid4())) as session:
        await session.prompt('continue')
    assert actions == ['new', 'prompt', ('load', 'saved-acp'), 'prompt']
    from sec_agent.agent_runtime.harness_acp_session import completed_recovery
    assert completed_recovery(tmp_path, previous_run_id=run, binding=common['binding'])['text'] == 'Public answer'
    assert completed_recovery(tmp_path, previous_run_id=str(uuid4()), binding=common['binding']) is None
    with pytest.raises(ValueError, match='binding_mismatch'):
        completed_recovery(tmp_path, previous_run_id=run, binding={'task': 'wrong'})
    with pytest.raises(ValueError, match='binding_mismatch'):
        async with admitted_acp_session(**{**common, 'binding': {'task': 'another'}}, run_id=str(uuid4())):
            pass


@pytest.mark.anyio
async def test_cancel_revokes_before_acp_cancel_and_uncertain_turn_is_not_retried(tmp_path):
    import asyncio
    from acp.schema import InitializeResponse, NewSessionResponse
    steps = []
    @asynccontextmanager
    async def spawn(client, *args, **kwargs):
        class Connection:
            async def initialize(self, **kw):
                return InitializeResponse(protocolVersion=1)
            async def new_session(self, **kw):
                return NewSessionResponse(sessionId='native-session')
            async def prompt(self, **kw):
                raise asyncio.CancelledError()
            async def cancel(self, **kw):
                steps.append('cancel')
        yield Connection(), None
    async with admitted_acp_session(binary='fixture', arguments=[], environment={}, directory=tmp_path,
            binding={'task': 'task'}, run_id=str(uuid4()), authority=lambda: None,
            stop=lambda: steps.append('stop'), mcp_servers=[], spawn=spawn) as session:
        with pytest.raises(asyncio.CancelledError):
            await session.prompt('task')
        assert steps == ['stop', 'cancel']
        with pytest.raises(RuntimeError, match='requires_recovery'):
            await session.prompt('task')


@pytest.mark.anyio
async def test_edit_conflict_is_atomic_actionable_and_does_not_stop_consultation(tmp_path):
    from sec_agent.agent_runtime.harness_artifact_tools import artifact_tools
    from sec_agent.agent_runtime.working_memory import WorkingMemory
    from test_on_demand_research import artifact_fixture, report
    artifacts = artifact_fixture()
    candidate = {k: v for k, v in report(artifacts).items() if k != 'citations'}
    memory = WorkingMemory(tmp_path/'notes.sqlite', owner='test', workspace='task', actor='lead')
    grants = artifact_tools(artifacts=lambda _:artifacts, memory=memory, delivery_intent='report', require_review=False)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'tools.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=grants,checkpointer=saver,thread_id='t',check=lambda:None,stop_on_tool_error=True)
        await bridge.initialize({'question':'task','messages':[]})
        await bridge.execute('save_research_report',{'report':candidate,'base_version':0})
        before = await bridge.state()
        old = candidate['narrative_markdown']
        result = await bridge.execute('edit_research_report',{'base_version':1,'edits':[
            {'old_str':old, 'new_str':old+' First proposed change'},
            {'old_str':old[40:80]+' transcription typo', 'new_str':'Second proposed change'}]})
        feedback = json.loads(result.content)
        assert result.status=='success' and feedback['saved'] is False
        assert feedback['status']=='edit_not_applied' and feedback['edit_index']==1
        assert feedback['candidate_view']=='saved_report_before_batch'
        after = await bridge.state()
        assert after['report']==before['report'] and after['report_version']==1
        assert not after.get('delivery')
        bridge.model_access()  # no failure latch for an ordinary edit conflict
        readback=await bridge.execute(feedback['readback']['tool'],feedback['readback']['arguments'])
        assert json.loads(readback.content)['report_version']==1
        corrected=await bridge.execute('edit_research_report',{'base_version':1,'edits':[
            {'old_str':old,'new_str':old.replace('explicitly scoped','carefully scoped')}]})
        assert json.loads(corrected.content)['saved'] is True
        # Genuine unbound-source validation still blocks further model dispatch.
        bad=await bridge.execute('edit_research_report',{'base_version':2,'edits':[
            {'old_str':old.replace('explicitly scoped','carefully scoped'),
             'new_str':old.replace('explicitly scoped','carefully scoped')+' [P99:INVALID]'}]})
        assert bad.status=='error'


def test_report_edit_location_hints_never_apply_ambiguous_or_near_matches():
    from sec_agent.agent_runtime.report_synthesis_agent import ReportEditMatchError, ReportTextEdit, apply_report_edits
    original={'title':'Test report','narrative_markdown':'A matching passage. A matching passage.'}
    with pytest.raises(ReportEditMatchError) as found:
        apply_report_edits(original,[ReportTextEdit(old_str='A matching passage.',new_str='Replacement')])
    assert len(found.value.feedback['candidates'])==2
    assert found.value.feedback['batch_preview_match_count']==2
    assert original['narrative_markdown']=='A matching passage. A matching passage.'
    with pytest.raises(ReportEditMatchError) as found:
        apply_report_edits(original,[ReportTextEdit(old_str='No shared evidence here',new_str='Replacement')])
    assert found.value.feedback['candidates']==[]


@pytest.mark.anyio
async def test_saved_report_versions_edits_citations_and_delivery_survive_restart(tmp_path):
    from sec_agent.agent_runtime.harness_artifact_tools import artifact_tools
    from sec_agent.agent_runtime.working_memory import WorkingMemory
    from test_on_demand_research import artifact_fixture, report
    artifacts = artifact_fixture()
    candidate = {k: v for k, v in report(artifacts).items() if k != 'citations'}
    memory = WorkingMemory(tmp_path / 'notes.sqlite', owner='test', workspace='task', actor='lead')
    grants = artifact_tools(artifacts=lambda _: artifacts, memory=memory, delivery_intent='report', require_review=False)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='task', check=lambda: None)
        await bridge.initialize({'question': 'task', 'messages': []})
        malformed = {**candidate, 'title': 'x'}
        rejected = await bridge.execute('save_research_report', {'report': malformed, 'base_version': 0})
        assert rejected.status == 'error'
        assert (await bridge.state())['report_draft'] == malformed
        assert not (await bridge.state()).get('report')
        saved = await bridge.execute('repair_report_fields', {'fields': {'title': candidate['title']}, 'base_version': 0})
        assert saved.status == 'success', saved.content
        before = (await bridge.state())['report']
        assert before['citations']
        # Duplicate/old version cannot overwrite current content or count as delivery.
        stale = await bridge.execute('save_research_report', {'report': candidate, 'base_version': 0})
        assert stale.status == 'error'
        assert not (await bridge.state()).get('delivery')
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='task', check=lambda: None)
        await bridge.initialize({})
        old = candidate['narrative_markdown']
        saved = await bridge.execute('edit_research_report', {'base_version': 1, 'edits': [
            {'old_str': old, 'new_str': old.replace('explicitly scoped', 'carefully scoped')}]})
        assert saved.status == 'success', saved.content
        after = await bridge.state()
        assert after['report']['citations'] == before['citations']
        assert after['report_version'] == 2
        final = await bridge.execute('deliver_current_report', {'version': 2})
        assert final.status == 'success'
        assert (await bridge.state())['delivery']['artifact_version'] == 2
        await bridge.begin_command('new-question')
        assert (await bridge.state())['delivery'] is None
        assert (await bridge.state())['report_version'] == 2


@pytest.mark.anyio
async def test_current_report_field_changes_keep_versions_and_invalid_chart_proposals(tmp_path):
    from sec_agent.agent_runtime.harness_artifact_tools import artifact_tools
    from sec_agent.agent_runtime.working_memory import WorkingMemory
    from test_on_demand_research import artifact_fixture, report
    artifacts = artifact_fixture()
    candidate = {k: v for k, v in report(artifacts).items() if k != 'citations'}
    memory = WorkingMemory(tmp_path / 'notes.sqlite', owner='test', workspace='task', actor='lead')
    grants = artifact_tools(artifacts=lambda _: artifacts, memory=memory, delivery_intent='report', require_review=False)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'tools.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='task', check=lambda: None)
        await bridge.initialize({'messages': []})
        schema = json.loads((await bridge.execute('read_current_report', {'field': 'schema'})).content)
        assert 'source' in schema['schema']['$defs']['ChartPoint']['required']
        assert 'value' not in schema['schema']['$defs']['ChartPoint']['properties']
        assert (await bridge.execute('save_research_report', {'report': candidate, 'base_version': 0})).status == 'success'
        original = (await bridge.state())['report']
        changed = await bridge.execute('repair_report_fields', {'fields': {'title': 'Current report field update'}, 'base_version': 1})
        assert changed.status == 'success', changed.content
        current = (await bridge.state())['report']
        assert current['narrative_markdown'] == original['narrative_markdown']
        assert current['citations'] == original['citations']
        assert (await bridge.state())['report_version'] == 2
        stale = await bridge.execute('repair_report_fields', {'fields': {'title': 'Stale title update'}, 'base_version': 1})
        assert stale.status == 'error'
        chart = {'title': 'Original chart proposal', 'unit': '%', 'points': [
            {'label': 'A', 'value': 1}, {'label': 'B', 'value': 2}],
            'sources': ['REF-a', 'REF-b'], 'interpretation': 'Original author interpretation.'}
        invalid = await bridge.execute('repair_report_fields', {'fields': {'charts': [chart]}, 'base_version': 2})
        assert invalid.status == 'error'
        state = await bridge.state()
        assert state['report'] == current and state['report_version'] == 2
        assert state['report_draft']['charts'] == [chart]  # no source guessing or deletion
        assert not state.get('delivery')
        assert json.loads(invalid.content)['schema_readback']['arguments'] == {'field': 'schema'}
        repaired = await bridge.execute('repair_report_fields', {'fields': {'charts': []}, 'base_version': 2})
        assert repaired.status == 'success'
        assert (await bridge.state())['report_version'] == 3
        assert (await bridge.state())['report_draft'] is None

@pytest.mark.anyio
async def test_supervised_read_pages_and_blocks_dispatch_after_a_failed_batch_member(tmp_path):
    from types import SimpleNamespace
    from sec_agent.agent_runtime.organization_work_session import observed_source_tool
    source = 'PASSAGE::fixture'
    body = 'A' * 12000 + 'remaining original'
    reader = SimpleNamespace(source_snapshot=lambda: {source: {'result_state':'source_bound_passage', 'text':body}})
    grant = observed_source_tool(lambda *_args, **_kwargs: reader, lambda: None)
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path/'paging.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=[grant], checkpointer=saver, thread_id='t', check=lambda: None,
                                      stop_on_tool_error=True)
        await bridge.initialize({'messages': []})

        async def read(**arguments):
            response = await bridge.call_tool(None, SimpleNamespace(name='read_research_source',
                                              arguments={'source_id':source, **arguments}))
            return json.loads(response.content[0].text)

        first = (await read(max_characters=14000))['result']
        assert first['next_offset'] == 12000 and first['page_limit_characters'] == 12000
        bridge.model_access()
        failed = await read(offset=-1)
        assert failed['status'] == 'error' and 'next_offset' in failed['result']
        tail = (await read(offset=first['next_offset']))['result']
        assert first['text'] + tail['text'] == body and tail['next_offset'] is None
        with pytest.raises(RuntimeError, match=failed['receipt_id']):
            bridge.model_access()


@pytest.mark.anyio
async def test_manuscript_preview_preserves_display_handles_and_can_be_read_back(tmp_path):
    from sec_agent.agent_runtime.quantitative_prose import quantitative_prose_tool
    from sec_agent.agent_runtime.source_references import reference_handle
    source = 'PASSAGE::fixture::document'
    base = f'Both districts recorded fewer repairs [{reference_handle(source)}].'
    proposed = base.replace('Both districts', 'Two districts')
    preview = quantitative_prose_tool(base, lambda: (base, 'Both districts recorded fewer repairs last year.'))
    readback = next(g for g in conversation_tools(thread_id='t') if g.tool.name == 'read_saved_result')
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'preview.sqlite')) as saver:
        bridge = HarnessBusinessTools(grants=[preview, readback], checkpointer=saver, thread_id='t', check=lambda: None)
        await bridge.initialize({'messages': []})
        receipt = await bridge.execute(preview.tool.name, {'edits':[{'before':base, 'after':proposed}]})
        assert receipt.status == 'success' and json.loads(receipt.content)['related_wording'][0]['excerpt'] == proposed
        reread = await bridge.execute('read_saved_result', {'tool_call_id':receipt.tool_call_id})
        assert reread.status == 'success' and 'related_wording' in reread.content
