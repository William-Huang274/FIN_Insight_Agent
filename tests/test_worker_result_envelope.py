import asyncio
import json
from copy import deepcopy

import pytest

from sec_agent.research_foundation.method_submission import decode_submission, SubmissionRejected
from sec_agent.research_foundation.method_worker import WorkerAction, compile_method_worker
from test_method_review import output


def test_complete_result_envelope_preserves_every_field_and_raw_response():
    body=output()['result']; original=deepcopy(body)
    action,receipt=decode_submission(json.dumps(body),WorkerAction)
    assert action.action=='finish' and action.calculations==[] and body==original
    record=receipt['runtime_parsing'][0]
    assert record['origin']=='runtime_compatibility_parse'
    assert record['normalized_result']['result']==body
    assert not record['financial_semantics_verified']
    assert json.loads(receipt['raw_response'])==original


@pytest.mark.parametrize('mutation', ['action','calculations','result','unknown','incomplete'])
def test_ambiguous_partial_or_mixed_result_never_gets_wrapped(mutation):
    body=output()['result']
    if mutation=='incomplete': body.pop('summary')
    elif mutation=='action': body['action']='calculate'
    elif mutation=='calculations': body['calculations']=[]
    elif mutation=='result': body['result']=None
    else: body['unrecognized_field']='extra'
    with pytest.raises(SubmissionRejected) as exc: decode_submission(body,WorkerAction)
    assert not exc.value.receipt['runtime_parsing']
    assert not exc.value.receipt['executed']


def test_bare_result_runs_in_native_worker_without_second_call_or_text_repair():
    calls=[];events=[];body=output()['result']
    async def call(actor,payload,schema):
        calls.append(actor)
        return json.dumps(body)
    graph=compile_method_worker(call=call,actor='worker',payload={'read_results':[], 'instructions':'Task'},
                                record=lambda event,value:events.append((event,value)),runtime_submissions=True)
    state=asyncio.run(graph.ainvoke({'observations':[],'tool_rounds':0}))
    assert calls==['worker'] and state['action']['action']=='finish'
    assert events[0][1]['runtime_parsing'][0]['normalized_result']['result']==body
    assert state['observations']==[]
