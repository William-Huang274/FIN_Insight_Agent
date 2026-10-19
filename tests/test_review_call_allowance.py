"""Request ceilings do not revoke tools from an already authorized response."""
import asyncio
import json
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain.agents.middleware.types import ModelRequest
from mcp import Client
import pytest

from sec_agent.agent_runtime.case_review_agent import ReviewCallAllowance, build_case_reviewer, case_mcp_tools
from test_research_convergence import artifact_fixture
from test_research_mcp import _build_server


def test_allowance_counts_current_request_explicitly_without_changing_tools_or_system():
    history=[HumanMessage(content='Original research'),AIMessage(content='',additional_kwargs={'reasoning_content':'saved'})]
    tools=[object(),object()]
    request=ModelRequest(model=LastRead(),messages=history,tools=tools,system_message=SystemMessage(content='Stable role'),
        state={'messages':history,'thread_model_call_count':25,'run_model_call_count':1})
    projected=ReviewCallAllowance(2).request_with_budget(request)
    value=json.loads(projected.messages[-1].content)
    assert value['current_request_number']==2 and value['additional_requests_after_this_response']==0
    assert value['completed_requests_in_run']==1
    assert projected.tools==tools and projected.system_message==request.system_message
    assert projected.messages[:-1]==history and len(history)==2
    assert 'closeout' not in projected.messages[-1].content


class LastRead(BaseChatModel):
    calls: int=0
    accepted_requests: int=1
    snapshots: list=[]
    seen: list=[]
    tools_seen: list=[]
    paper: str='P01'
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
            'name':'read_research_artifact','id':'last-read','args':{'paper_id':self.paper},'type':'tool_call'}]))])


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
        assert json.loads(model.seen[-1].content)['additional_requests_after_this_response']==0
    asyncio.run(run())


def test_two_request_run_keeps_tools_and_replaces_allowance_instead_of_accumulating():
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
            assert len(notices)==1
            value=json.loads(notices[0].content)
            assert value['current_request_number']==index
            assert value['additional_requests_after_this_response']==2-index
        assert not any('runtime_model_call_allowance' in m.content for m in result['messages']
            if isinstance(m,HumanMessage))
    asyncio.run(run())
