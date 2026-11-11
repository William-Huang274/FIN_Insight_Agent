from types import SimpleNamespace
from langchain_core.messages import AIMessage, ToolMessage
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.harness_business_tools import restored_batch_feedback
from sec_agent.research_foundation.source_bound_calculator import sources_from_receipts


def test_read_failed_write_is_inspection_not_reexecution_or_evidence():
    reader=next(g.tool for g in conversation_tools(thread_id='fixture') if g.tool.name=='read_saved_result')
    failed=ToolMessage(content='new_source_observation_conflict', name='edit_research_report',
        tool_call_id='failed-write',status='error')
    result=reader.func(tool_call_id='failed-write',runtime=SimpleNamespace(state={'messages':[failed]}),
        max_characters=10)
    assert result['original_status']=='error'
    assert result['result_state']=='saved_failure_receipt' and result['source_evidence'] is False
    assert result['new_tool_dispatch'] is False and result['next_offset']==10
    assert result['content']=='new_source'
    assert sources_from_receipts([{'status':'success','name':'read_saved_result','artifact':result}])=={}
    assert failed.status=='error' and failed.content=='new_source_observation_conflict'


def test_recovery_returns_exact_failed_receipt_readback_without_marking_write_successful():
    old=ToolMessage(content='new_source_observation_conflict',name='edit_research_report',
        tool_call_id='failed-write',status='error')
    call=AIMessage(content='',tool_calls=[{'name':'read_saved_result',
        'args':{'tool_call_id':'failed-write'},'id':'inspect'}])
    failed=ToolMessage(content='old read rejection',name='read_saved_result',tool_call_id='inspect',status='error')
    result=restored_batch_feedback([old,call,failed],['inspect'])
    assert result['failures'][0]['available_original']['arguments']=={'tool_call_id':'failed-write'}
