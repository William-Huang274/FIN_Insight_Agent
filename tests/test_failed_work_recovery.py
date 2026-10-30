"""Native pending-task recovery, not reconstruction of model history."""
import asyncio
from copy import deepcopy

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END

from sec_agent.agent_runtime.conversation_agent import build_conversation_agent, GrantedTool
from sec_agent.agent_runtime.on_demand_research import OnDemandResearchState
from sec_agent.agent_runtime.native_subgraph_config import native_subgraph_config


def test_native_nested_resume_reuses_successes_and_retries_only_failed_task():
    calls = {'catalog': 0, 'search': 0}
    @tool
    def catalog():
        """Read the fixed catalog."""
        calls['catalog'] += 1
        return 'immutable-source-and-period'
    @tool
    async def search():
        """Search current sources."""
        calls['search'] += 1
        if calls['search'] == 1:
            # The sibling completed and its durable result was flushed before
            # the provider failure; uncommitted side effects aren't receipts.
            await asyncio.sleep(.1)
            raise RuntimeError('account_overdue')
        return 'source-backed-results'
    class Model(FakeMessagesListChatModel):
        def bind_tools(self, *a, **kw): return self
    model = Model(responses=[
        AIMessage(content='', tool_calls=[{'name': 'catalog', 'args': {}, 'id': 'ok'},
                                         {'name': 'search', 'args': {}, 'id': 'fail'}]),
        AIMessage(content='Research continued from both tool results.')])
    inner = build_conversation_agent(model=model, grants=[GrantedTool(t, 'read', 'fixed scope') for t in (catalog, search)],
        permission_mode='request_standard', checkpointer=None, server_managed_persistence=True)
    async def parent(state, config: RunnableConfig):
        config = native_subgraph_config(config)
        return await inner.ainvoke(state, config)
    middle = StateGraph(OnDemandResearchState)
    middle.add_node('parent', parent); middle.add_edge(START, 'parent'); middle.add_edge('parent', END)
    child = middle.compile()
    async def work(state, config: RunnableConfig):
        config = native_subgraph_config(config)
        return await child.ainvoke(state, config)
    outer = StateGraph(OnDemandResearchState)
    outer.add_node('work', work); outer.add_edge(START, 'work'); outer.add_edge('work', END)
    saver = InMemorySaver()
    graph = outer.compile(checkpointer=saver)
    config = {'configurable': {'thread_id': 'same-thread', 'run_id': 'first'}}
    async def run():
        with pytest.raises(RuntimeError, match='account_overdue'):
            await graph.ainvoke({'question': 'same question', 'messages': [('user', 'same question')]}, config)
        assert (await graph.aget_state(config)).next == ('work',)
        result = await graph.ainvoke(None, {'configurable': {'thread_id': 'same-thread', 'run_id': 'recovery'}})
        assert result['question'] == 'same question'
        assert len([m for m in result['messages'] if m.type == 'human']) == 1
        assert [m.content for m in result['messages'] if m.type == 'tool'] == ['immutable-source-and-period', 'source-backed-results']
        assert calls == {'catalog': 1, 'search': 2}
        assert model.i == 0  # exactly two responses, no regenerated first call
    asyncio.run(run())


def test_recover_uses_native_resume_not_new_input_or_checkpoint_fork(root):
    from sec_agent.agent_runtime.organization_report_action_contract import action_request, validate_baseline
    from sec_agent.agent_runtime.organization_continuation_contract import baseline_digest
    s = root
    s.action_body['action'] = 'recover'
    s.baseline['next'] = ['work']
    s.baseline['metadata'] = {'run_id': s.action_body['previous_run_id']}
    s.action_body['state_digest'] = baseline_digest(s.baseline)
    validate_baseline(s.baseline, s.action_grant)
    args = action_request(s.intake.threads[s.grant['execution_id']], s.action_grant)
    assert args['input'] is None and 'checkpoint_id' not in args
    bad = deepcopy(s.baseline); bad['next'] = []
    with pytest.raises(ValueError): validate_baseline(bad, s.action_grant)


from test_organization_root_actions import root
from test_organization_work_session import continuous
from test_organization_native_drafts import organization
from test_java_research_intake import intake
