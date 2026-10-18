from copy import deepcopy
import json

import pytest
from pydantic import BaseModel
from typing import Literal

from sec_agent.agent_runtime.native_tool_arguments import complete_action_tag
from sec_agent.agent_runtime.specialist_graph import RequestCalculationAction
from sec_agent.agent_runtime.tool_recovery import recheck_failed_calculation
from test_specialist_tool_batch import _exercise
from test_tool_recovery import failed_state, rehash


def test_only_absent_unique_constant_is_completed_without_mutating_original():
    args={'request': {'expression': 'x'}}; before=deepcopy(args)
    result, repairs=complete_action_tag(RequestCalculationAction,args)
    assert result=={**args,'action':'request_calculation'} and args==before
    assert repairs[0]['original_arguments_preserved']
    for value in ('wrong',None,''):
        explicit={**args,'action':value}
        assert complete_action_tag(RequestCalculationAction,explicit)==(explicit,[])
    class Ambiguous(BaseModel):
        action: Literal['a','b']
    assert complete_action_tag(Ambiguous,args)==(args,[])
    assert complete_action_tag(None,args)==(args,[])


def test_native_dispatch_keeps_raw_call_and_reports_identity_completion():
    def missing(batch):
        for call in batch['tool_calls']:call['args'].pop('action')
    result,requests,calls=_exercise(missing)
    assert len(calls)==4
    assert all('action' not in c['args'] for c in result['notebook']['model_turn_records'][0]['action']['tool_calls'])
    for receipt in requests[1]['tool_results']:
        assert receipt['status']=='success'
        body=json.loads(receipt['content'])
        assert body['argument_normalizations'][0]['reason']=='missing_unique_tool_action_constant'


@pytest.mark.parametrize('defect',['conflict','null','context','extra','required'])
def test_completion_does_not_hide_other_errors_or_relax_permissions(defect):
    def mutate(batch):
        args=batch['tool_calls'][0]['args'];args.pop('action')
        if defect=='conflict':args['action']='request_finance'
        if defect=='null':args['action']=None
        if defect=='context':args['context_digest']='0'*64
        if defect=='extra':args['unexpected']=True
        if defect=='required':args.pop('reason_summary')
    _,requests,calls=_exercise(mutate)
    assert len(calls)==3 and requests[1]['tool_results'][0]['status']=='error'
    _,requests,calls=_exercise(lambda b:b['tool_calls'][-1]['args'].pop('action'),source_enabled=False)
    assert len(calls)==3 and requests[1]['tool_results'][-1]['status']=='error'


def test_local_recovery_executes_saved_calculation_and_keeps_error_and_budget(monkeypatch):
    with monkeypatch.context() as legacy:
        legacy.setattr('sec_agent.agent_runtime.native_tool_arguments.complete_action_tag',lambda m,a:(a,[]))
        state=failed_state(omit_action=True)
    state['tool_results'][0]['content']=json.dumps({'feedback':[{'code':'specialist_tool_arguments_invalid'}]})
    rehash(state); before=deepcopy(state)
    restored=recheck_failed_calculation(state,'failed-calc')
    check=restored['task_context']['tool_recovery_checks'][-1]
    assert check['outcome']['status']=='success'
    assert check['outcome']['result']['value_decimal']=='0.6'
    assert check['argument_normalizations'][0]['value']=='request_calculation'
    assert state==before and restored['tool_results']==state['tool_results']
    assert restored['notebook']['model_turn_count']==state['notebook']['model_turn_count']
    assert restored['max_model_turns']==state['max_model_turns']
    assert recheck_failed_calculation(restored,'failed-calc')==restored
