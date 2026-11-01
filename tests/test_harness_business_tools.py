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
        computed = await second.execute('calculate_research_metric', params)
        assert computed.status == 'success', computed.content
        assert computed.artifact['value_decimal'] == '60'
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
