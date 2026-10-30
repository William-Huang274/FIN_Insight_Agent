"""Authorized checkpoint recovery, without changing paid research history."""
import asyncio

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda, RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END

from sec_agent.agent_runtime.model_context import RequestSummaryState, resume_failed_summary
from sec_agent.agent_runtime.native_subgraph_config import native_subgraph_config
from tests.test_request_summary import history, policy


def test_explicit_recovery_reenters_summary_once_and_preserves_failed_checkpoint():
    async def run():
        attempts = []
        permit = [None]
        succeeds = [False]
        middleware = policy([])

        async def summarize(value):
            attempts.append(value)
            if not succeeds[0]:
                raise TimeoutError('original failure')
            return AIMessage(content='Preserved task and evidence; original source P01:S0 remains readable.')

        middleware.native._summary_model = RunnableLambda(summarize)

        class Guard(AgentMiddleware):
            def before_model(self, state, runtime):
                return None

            async def awrap_model_call(self, request, handler):
                if request.state.get('request_summary_failure'):
                    raise ValueError('original_input_too_large')
                return await handler(request)

        snapshots = []

        async def parent(state, config: RunnableConfig):
            agent = create_agent(FakeListChatModel(responses=['Research continued']),
                                 middleware=[Guard(), middleware])
            cfg = native_subgraph_config(config)
            recovered = await resume_failed_summary(agent, cfg, permit[0])
            snapshots.append(await agent.aget_state(cfg))
            result = await agent.ainvoke(None if recovered else state, cfg)
            return result

        graph = StateGraph(RequestSummaryState)
        graph.add_node('parent', parent)
        graph.add_edge(START, 'parent'); graph.add_edge('parent', END)
        saver = InMemorySaver()
        app = graph.compile(checkpointer=saver)
        config = {'configurable': {'thread_id': 'summary-recovery'}}
        rows = history()
        with pytest.raises(ValueError, match='original_input_too_large'):
            await app.ainvoke({'messages': rows}, config)
        assert len(attempts) == 1
        # Ordinary resume cannot silently spend on the failed summary again.
        with pytest.raises(ValueError, match='original_input_too_large'):
            await app.ainvoke(None, config)
        assert len(attempts) == 1
        permit[0] = 'authorized-command-1'
        with pytest.raises(ValueError, match='original_input_too_large'):
            await app.ainvoke(None, config)
        assert len(attempts) == 2
        with pytest.raises(ValueError, match='original_input_too_large'):
            await app.ainvoke(None, config)
        assert len(attempts) == 2  # same signed command is already consumed
        succeeds[0] = True
        permit[0] = 'authorized-command-2'
        result = await app.ainvoke(None, config)
        assert len(attempts) == 3 and result['request_summary']['count'] == 1
        assert result['messages'][:len(rows)] == rows
        assert result['messages'][-1].content == 'Research continued'
        assert result['request_summary_recovery_id'] == permit[0]
        assert any(c.checkpoint['channel_values'].get('request_summary_failure')
                   for c in saver.list(None))

    asyncio.run(run())
