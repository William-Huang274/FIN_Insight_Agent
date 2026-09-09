import asyncio
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.conversation_knowledge import knowledge_tools
from test_conversation_agent import ScriptedTools


def fixture():
    thread, checkpoint = str(uuid4()), str(uuid4())
    item = {"passage_id":"PASSAGE::fixture", "passage":"Revenue 125 USD for the full year.",
        "title":"Synthetic source", "result_state":"source_bound_passage", "writer_citable":True,
        "numeric_fact_authority":False, "source_url":"https://example.com/filing"}
    class Store:
        values = None
        def __init__(self): self.values={}; self.writes=0
        async def get_item(self, ns, key): return deepcopy(self.values.get((tuple(ns),key)))
        async def put_item(self,ns,key,value,**kwargs):
            self.writes+=1
            self.values[(tuple(ns),key)]={"key":key,"value":deepcopy(value)}
        async def search_items(self,ns,limit,offset):
            return {"items":[deepcopy(v) for (namespace,_),v in self.values.items() if namespace==tuple(ns)][offset:offset+limit]}
    class Threads:
        owner="alice"
        async def get(self, tid):
            assert tid==thread
            return {"metadata":{"surface":"finsight_general_conversation","owner_id":self.owner}}
        async def get_state(self,tid,**kwargs):
            assert tid==thread
            if kwargs: assert kwargs['checkpoint']['checkpoint_id']==checkpoint
            return {"checkpoint":{"checkpoint_id":checkpoint},"values":{"messages":[{
                "type":"tool","status":"success","name":"read_public_source",
                "artifact":{"operation":"search","items":[item]}}]}}
    return SimpleNamespace(store=Store(),threads=Threads()),thread,item


@pytest.mark.parametrize("mode",["request_standard","approve_for_me","full_access"])
def test_native_approval_before_personal_admission_and_exact_cross_thread_read(mode):
    sdk, thread, item = fixture()
    async def run():
        grants=knowledge_tools(sdk=sdk,owner_id="alice",thread_id=thread)
        model=ScriptedTools(responses=[AIMessage(content="",tool_calls=[{
            "name":"save_sources_to_knowledge","args":{"source_ids":[item['passage_id']],"purpose":"Future source verification"},
            "id":"save","type":"tool_call"}]),AIMessage(content="Saved")])
        agent=build_conversation_agent(model=model,grants=grants,permission_mode=mode,checkpointer=InMemorySaver())
        config={"configurable":{"thread_id":thread}}
        pending=await agent.ainvoke({"messages":[HumanMessage(content="Keep the source with my approval")]},config)
        assert pending['__interrupt__'] and sdk.store.writes==0
        await agent.ainvoke(Command(resume={"decisions":[{"type":"approve"}]}),config)
        assert sdk.store.writes==1
        other={g.tool.name:g.tool for g in knowledge_tools(sdk=sdk,owner_id="alice",thread_id=str(uuid4()))}
        import json
        listed=await other['list_saved_knowledge'].ainvoke({})
        key=listed['items'][0]['knowledge_id']
        body=json.loads(await other['read_saved_knowledge'].ainvoke({'knowledge_id':key}))
        assert body['source_items'][item['passage_id']]==item
        bob={g.tool.name:g.tool for g in knowledge_tools(sdk=sdk,owner_id="bob",thread_id=str(uuid4()))}
        assert not (await bob['list_saved_knowledge'].ainvoke({}))['items']
        assert '没有' in await bob['read_saved_knowledge'].ainvoke({'knowledge_id':key})
        sdk.threads.owner='bob'
        assert '授权范围' in await other['read_saved_knowledge'].ainvoke({'knowledge_id':key})
    asyncio.run(run())
