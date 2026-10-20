"""Request ceilings do not revoke tools from an already authorized response."""
import asyncio
import json
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain.agents.middleware.types import ModelRequest
from mcp import Client
import pytest

from sec_agent.agent_runtime.case_review_agent import build_case_reviewer, case_mcp_tools
from sec_agent.agent_runtime.confirmation_reading import ReviewReadingContext
from test_research_convergence import artifact_fixture
from test_research_mcp import _build_server


def test_legacy_countdown_exits_request_without_changing_tools_or_journal():
    history=[HumanMessage(content='Original research'),AIMessage(content='',additional_kwargs={'reasoning_content':'saved'})]
    tools=[object(),object()]
    request=ModelRequest(model=LastRead(),messages=history,tools=tools,system_message=SystemMessage(content='Stable role'),
        state={'messages':history,'thread_model_call_count':25,'run_model_call_count':1})
    countdown=HumanMessage(content=json.dumps({'origin':'runtime_model_call_allowance', 'additional_requests_after_this_response':0}))
    request=request.override(messages=[*history,countdown])
    projected=ReviewReadingContext(artifact_fixture()).project(request)
    assert projected.tools==tools and projected.system_message==request.system_message
    assert projected.messages==history and request.messages[-1]==countdown


class LastRead(BaseChatModel):
    calls: int=0
    accepted_requests: int=1
    snapshots: list=[]
    seen: list=[]
    tools_seen: list=[]
    paper: str='P01'
    tool_name: str='read_research_artifact'
    @property
    def _llm_type(self):return 'offline-final-authorized-read'
    def bind_tools(self,tools,**kwargs):
        self.tools_seen=[t.name for t in tools]
        return self
    def _generate(self,messages,stop=None,run_manager=None,**kwargs):
        assert self.calls<self.accepted_requests,'Request ceiling must stop dispatch'
        self.calls+=1;self.seen=list(messages)
        self.snapshots.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content='',tool_calls=[{
            'name':self.tool_name,'id':'last-read','args':{'paper_id':self.paper},'type':'tool_call'}]))])


@pytest.mark.parametrize('paper,expected_status',[('P01','success'),('UNKNOWN','error')])
def test_final_authorized_response_executes_tool_and_stops_before_next_model(paper,expected_status):
    async def run():
        artifacts=artifact_fixture();model=LastRead(paper=paper)
        history=[HumanMessage(content='Continue current review.'),
            ToolMessage(name='read_research_artifact',tool_call_id='previous-read',content='saved paper',
                artifact={'paper_id':'P01','section':'workpaper','content':artifacts.read_paper('P01')})]
        async with Client(_build_server(case_artifacts=artifacts),raise_exceptions=False) as client:
            agent=build_case_reviewer(role='verifier',model=model,tools=await case_mcp_tools(client),
                artifacts=artifacts,max_model_calls=1)
            result=await agent.ainvoke({'messages':history})
        assert model.calls==1 and 'read_research_artifact' in model.tools_seen
        assert result['thread_model_call_count']==1 and not result.get('review')
        reply=next(m for m in result['messages'] if isinstance(m,ToolMessage) and m.tool_call_id=='last-read')
        assert reply.status==expected_status
        assert 'closeout reserve' not in reply.content
        assert any(m.tool_call_id=='previous-read' and m.artifact==history[1].artifact
            for m in result['messages'] if isinstance(m,ToolMessage))
        assert not any('runtime_model_call_allowance' in str(m.content) or 'Budget: up to' in str(m.content) for m in model.seen)
    asyncio.run(run())


def test_two_request_run_enforces_limit_without_countdown():
    async def run():
        artifacts=artifact_fixture(); model=LastRead(accepted_requests=2)
        async with Client(_build_server(case_artifacts=artifacts),raise_exceptions=False) as client:
            agent=build_case_reviewer(role='verifier',model=model,tools=await case_mcp_tools(client),
                artifacts=artifacts,max_model_calls=2)
            result=await agent.ainvoke({'messages':[HumanMessage(content='Read within two requests.')]})
        assert model.calls==2 and not result.get('review')
        for index,messages in enumerate(model.snapshots,1):
            notices=[m for m in messages if isinstance(m,HumanMessage)
                and 'runtime_model_call_allowance' in m.content]
            assert notices==[]
        assert not any('runtime_model_call_allowance' in m.content for m in result['messages']
            if isinstance(m,HumanMessage))
    asyncio.run(run())


@pytest.mark.parametrize('role', ['decision', 'synthesis', 'writer', 'lead_writer', 'verifier'])
@pytest.mark.parametrize('allowance', [1, 2])
def test_output_roles_keep_internal_ceiling_out_of_model_instructions(role, allowance):
    from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent

    async def run():
        model = LastRead(accepted_requests=allowance, tool_name='read_current_workpaper')
        agent = build_case_output_agent(
            role=role, model=model, tools=[], artifacts=artifact_fixture(),
            limits={'model_calls': allowance, 'tool_calls': 8},
            incomplete_reviewers=[],
        )
        result = await agent.ainvoke({'messages': [HumanMessage(content='Continue the current research.')]})
        assert model.calls == allowance
        assert not result.get('output')
        receipts = [m for m in result['messages'] if isinstance(m, ToolMessage)]
        assert len(receipts) == allowance and all(m.status == 'success' for m in receipts)
        for messages in model.snapshots:
            system = '\n'.join(str(m.content) for m in messages if isinstance(m, SystemMessage))
            assert 'Budget:' not in system
            assert 'model calls/' not in system
            assert 'calls left' not in system
        assert 'read_current_workpaper' in model.tools_seen

    asyncio.run(run())
