"""The server's non-execution graph must decode both persisted contracts."""
import asyncio
from types import SimpleNamespace

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END

from sec_agent.agent_runtime.on_demand_research import OnDemandResearchState
from sec_agent.agent_runtime.research_session import ResearchSessionState
from sec_agent.agent_runtime.research_session_runtime import research_session_graph


def test_server_read_graph_retains_continuous_and_historical_channels():
    async def run():
        saver = InMemorySaver()
        cases = [
            (OnDemandResearchState, {'question': 'Current research question', 'messages': [HumanMessage(content='Current request')],
                'delivery': {'artifact_kind': 'workpaper', 'artifact_id': 'note', 'artifact_version': 3},
                'task_outcome': {'execution_status': 'submitted'}, 'parent_calls': 4,
                'request_summary': {'summary': 'Current understanding'}, 'operation_records': []}),
            (ResearchSessionState, {'question': 'Historical report question', 'phase': 'ready_for_human_review',
                'report': {'title': 'Historical report'}, 'report_version': 2,
                'research_orientation': {'findings': []}, 'conversation': [{'role': 'user', 'content': 'Old question'}],
                'model_events': [{'event': 'saved'}]}),
        ]
        for i, (schema, value) in enumerate(cases):
            writer = StateGraph(schema)
            writer.add_node('write', lambda state: {})
            writer.add_edge(START, 'write'); writer.add_edge('write', END)
            config = {'configurable': {'thread_id': str(i)}}
            persisted = await writer.compile(checkpointer=saver).ainvoke(value, config)
            async with research_session_graph({}, SimpleNamespace(execution_runtime=None)) as reader:
                reader.checkpointer = saver
                result = await reader.aget_state(config)
            for key in value:
                assert result.values[key] == persisted[key], key
            assert result.values == persisted  # no invented empty old/new fields
    asyncio.run(run())
