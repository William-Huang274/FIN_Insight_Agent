"""Lossless transport recovery, not automatic research approval."""
import asyncio
from copy import deepcopy
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from sec_agent.agent_runtime.case_review_agent import InvalidToolCallFeedback, build_case_reviewer
from test_case_review_agent import ScriptedNativeChat, call
from test_research_convergence import artifact_fixture
from test_review_inspection_recovery import reads


class RecoveryChat(ScriptedNativeChat):
    def bind_tools(self, tools, **kwargs):
        assert {'record_case_finding','submit_case_review'} <= {t.name for t in tools}
        return self


@pytest.mark.parametrize('tool,field', [('record_case_finding','finding'), ('submit_case_review','review')])
def test_decode_object_retains_original_and_changes_no_values(tool, field):
    value = {'classification': 'unresolved', 'quote': '原文\n"exact"', 'list': [1, None, {'a': 'b'}]}
    raw = json.dumps(value, ensure_ascii=False)
    message = AIMessage(content='', tool_calls=[call(tool,{field:raw},'one')],
                        additional_kwargs={'reasoning_content':'original reasoning'})
    before = deepcopy(message)
    recovered = InvalidToolCallFeedback().after_model({'messages':[message]},None)['messages'][0]
    assert message == before
    assert recovered.tool_calls[0]['args'] == {field:value}
    assert recovered.additional_kwargs == before.additional_kwargs
    receipt = recovered.response_metadata['tool_argument_recovery'][0]
    assert receipt['original_arguments'] == {field:raw}
    assert receipt['method'] == 'json_object_parameter'
    assert InvalidToolCallFeedback().after_model({'messages':[recovered]},None) is None


@pytest.mark.parametrize('raw', ['{"a":', '{"a":1,"a":2}', '{"x":{"a":1,"a":2}}',
    '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', '{} trailing', '{}}', '[]', 'null', '4', '"{}"', '```json\n{}\n```'])
def test_ambiguous_or_partial_object_string_stays_invalid(raw):
    message=AIMessage(content='',tool_calls=[call('record_case_finding',{'finding':raw},'bad')])
    assert InvalidToolCallFeedback().after_model({'messages':[message]},None) is None
    assert message.tool_calls[0]['args']['finding'] == raw


@pytest.mark.parametrize('problem', ['none','schema','quote','source','same_id','classification'])
def test_decoded_object_still_uses_native_validation(problem):
    async def exercise():
        a=artifact_fixture()
        f={'finding_id':'F1','paper_id':'P01','severity':'advisory',
           'problematic_quote':a.read_paper('P01')['thesis'],
           'diagnosis':'Synthetic diagnosis retained verbatim.',
           'requested_change':'Synthetic request retained verbatim.'}
        if problem=='schema':f['unexpected']='must not be dropped'
        if problem=='quote':f['problematic_quote']='This is not in the current paper.'
        if problem=='source':f['source_checks']=[{'source_id':'NOT_FOUND','quote':'nonexistent'}]
        calls=[call('record_case_finding',{'finding':json.dumps(f)},'encoded')]
        if problem=='same_id':calls.append(call('record_case_finding',{'finding':f},'object'))
        if problem=='classification':
            review={'summary':'Synthetic review with a contradictory completion.',
                    'assessments':[{'paper_id':'P01','assessment':'A synthetic unfinished check remains.'}],
                    'completion':'complete','unresolved_data_requests':['Necessary check not performed']}
            calls=[call('submit_case_review',{'review':json.dumps(review)},'encoded')]
        model=RecoveryChat(marker='recovery',replies=[calls])
        agent=build_case_reviewer(role='counter',model=model,tools=[],artifacts=a,max_model_calls=1)
        state=await agent.ainvoke({'messages':[HumanMessage(content='Synthetic only'), *reads(a)]})
        results=[m for m in state['messages'] if isinstance(m,ToolMessage) and m.tool_call_id in {'encoded','object'}]
        assert len(results)==len(calls)
        assert all((m.status=='error') == (problem!='none') for m in results), [m.content for m in results]
        assert bool(state.get('recorded_findings')) == (problem=='none')
        assert not state.get('review')
        if problem=='none':
            assert state['recorded_findings']['F1']['diagnosis']==f['diagnosis']
    asyncio.run(exercise())
