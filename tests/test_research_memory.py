import asyncio
from copy import deepcopy
from types import SimpleNamespace
import pytest
from sec_agent.agent_runtime.research_memory import remember_research,research_memory_tools


def test_fixed_version_memory_is_scoped_and_region_reads_do_not_mix_requirements(tmp_path,monkeypatch):
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH',str(tmp_path/'notes.sqlite'))
    saved={};seen=[]
    state={'checkpoint':{'checkpoint_id':'cp1'},'values':{'phase':'human_completed','report_version':2,
        'report':{'title':'ACME FY2025 observation','narrative_markdown':'Old fixed report',
            'citations':{'NUMFACT::one':{'sources':[{'value_decimal':'100','unit':'USD','period_end':'2025-12-31'}]}}}}}
    async def thread(tid):return {'status':'interrupted','metadata':{'owner_id':'alice'}}
    async def get_state(tid,**kwargs):seen.append(kwargs);return deepcopy(state)
    async def put(ns,key,value,**kwargs):saved[tuple(ns),key]={'value':deepcopy(value)}
    async def get(ns,key):return saved.get((tuple(ns),key))
    sdk=SimpleNamespace(threads=SimpleNamespace(get=thread,get_state=get_state),store=SimpleNamespace(put_item=put,get_item=get))
    async def run():
        ref=await remember_research(sdk,'research','alice')
        tool=research_memory_tools(sdk,'alice')[1].tool
        result=await tool.ainvoke({'memory_id':ref['memory_id'],'region':'numbers'})
        assert result['citation_bindings']['NUMFACT::one']['sources'][0]['value_decimal']=='100'
        assert seen[-1]['checkpoint']['checkpoint_id']=='cp1'
        result=await tool.ainvoke({'memory_id':ref['memory_id'],'region':'requirements'})
        assert result['body']=='' and 'not automatically' in result['notice']
        from sec_agent.agent_runtime.user_context import save_user_context
        assert save_user_context('alice','research','只做现金观察',0)['saved']
        revised=await remember_research(sdk,'research','alice')
        assert revised['memory_id']!=ref['memory_id']
        original=await tool.ainvoke({'memory_id':ref['memory_id'],'region':'requirements'})
        assert original['body']==''
        denied=await research_memory_tools(sdk,'bob')[1].tool.ainvoke({'memory_id':ref['memory_id']})
        assert '没有' in denied
        state['values']['phase']='research_needs_attention'
        with pytest.raises(ValueError):await remember_research(sdk,'research','alice')
    asyncio.run(run())
