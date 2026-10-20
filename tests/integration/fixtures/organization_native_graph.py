"""Real organization factory/graph with a scripted provider; qualification only.

No authority, SDK, native queue, checkpoint, source or permission implementation
is replaced. Trace export is disabled locally; the server still checks its license.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import time

if os.getenv('FIN_ORGANIZATION_GRAPH_QUALIFICATION') != '1':
    raise RuntimeError('isolated_organization_graph_qualification_only')
if os.getenv('OPENAI_API_KEY') or os.getenv('DEEPSEEK_API_KEY'):
    raise RuntimeError('provider_credentials_forbidden_in_static_qualification')

from langgraph.config import get_config
from pydantic import TypeAdapter
from sec_agent.agent_runtime import research_session_runtime as host, agent_server_entry
from sec_agent.agent_runtime.specialist_graph import SpecialistNativeToolBatch
from sec_agent.research_foundation.contracts import canonical_sha256


def forbidden(*args, **kwargs):
    raise AssertionError('static_organization_opened_unapproved_host_or_model')


def adapter(**kwargs):
    tid = get_config()['configurable']['thread_id']
    requests = []
    evidence = Path(os.environ['FIN_PROBE_EVIDENCE'])
    def turn(request):
        requests.append(request)
        count = len(requests)
        # The scripted adapter emits a real audit event explicitly marked as
        # no provider transport, so the BFF can distinguish known zero from missing.
        kwargs['audit_sink']({'event':'outcome','call_id':f'static:{tid}:{count}',
            'provider_call_attempted':False,'status':'qualification_no_provider','origin':'deterministic_fixture'})
        with (evidence/'model-turns.jsonl').open('a') as out:
            out.write(json.dumps({'thread_id':tid,'turn':count,'synthetic':True})+'\n')
        if not request.get('orientation_context'):
            assert count == 1
            note = 'Static continuation qualification stops with unfinished research, without claiming a financial result.'
            name, args = 'SubmitResearchHandoffAction', {'disposition':'needs_attention','reason_summary':note,
                'synthesis_notes':note,'acknowledged_incomplete_task_ids':[],
                'question_coverage':[{'question_quote':request['research_question'],'status':'unresolved','supporting_task_ids':[],'rationale':note}],
                'execution_plan':{'depth':'integrated','rationale':note,'omitted_steps_reason':note,'escalation_conditions':note}}
        elif count == 1:
            assert request['orientation_context']['source_space'] == 'organization'
            query = os.getenv('FIN_PROBE_ORGANIZATION_QUERY')
            name, args = 'RequestSourceAction', {'action':'request_source','reason_summary':'List pinned originals.',
                'selection':({'source_space':'organization','operation':'search','query':query} if query
                             else {'source_space':'organization','operation':'catalog'})}
        elif count == 2:
            result = json.loads(request['tool_results'][0]['content'])['result']
            if os.getenv('FIN_PROBE_ORGANIZATION_QUERY'):
                selection = result['items'][0]['readback']
            else:
                document = next(r['document_id'] for r in result['items'] if r.get('document_id'))
                selection = {'source_space':'organization','operation':'read','document_id':document}
            if 'Revoke during static model' in json.dumps(request):
                (evidence/(tid+'.ready')).write_text('static model response pending')
                deadline = time.monotonic()+45
                while not (evidence/(tid+'.release')).exists():
                    if time.monotonic()>deadline: raise AssertionError('revocation_barrier_timeout')
                    time.sleep(.1)
            name, args = 'RequestSourceAction', {'action':'request_source','reason_summary':'Read pinned original.',
                'selection':selection}
        elif count == 3:
            result = json.loads(request['tool_results'][0]['content'])['result']
            passage = next(r for r in result['items'] if r.get('result_state')=='source_bound_passage')
            name, args = 'SubmitResearchOrientationAction', {
                'reason_summary':'Static source-bound qualification, no financial conclusion.',
                'disposition':'needs_attention','overview':'Pinned original read; further research remains unassessed.',
                'findings':[{'finding_id':'F1','judgment':'The static original contains a test sentence.',
                    'kind':'observation','read_refs':['O2'],'unresolved':'Financial meaning is not assessed.',
                    'evidence_spans':[{'read_ref':'O2','passage_id':passage['passage_id'],'quote':passage['passage'][:600]}]}],
                'topics':[], 'scope_map':[{'question':'Further financial research','status':'needs_discovery','topic_ids':[],
                    'reason':'Only static evidence navigation is qualified.','revisit_when':'After separate research acceptance.'}],
                'coverage_and_gaps':'No financial quality assessment.',
                'graph_skip_reason':'This test authorizes only the fixed original; no external graph.',
                'recency_skip_reason':'This test fixes a historical original; no claim of current coverage.'}
        else:
            raise AssertionError('unexpected_static_model_turn:'+str(request.get('tool_results'))[:1000])
        action = TypeAdapter(SpecialistNativeToolBatch).validate_json(json.dumps({'action':'native_tool_batch',
            'context_digest':request['context_digest'],'tool_calls':[{'id':str(count),'name':name,
            'args':{'context_digest':request['context_digest'],**args}}]})).model_dump(mode='json')
        return {'action':action,'runtime_receipt':{'receipt_id':f'static:{tid}:{count}','kind':'model',
            'actor':request['agent_id'],'status':'success','request_digest':canonical_sha256(request),
            'output_digest':canonical_sha256(action),'elapsed_ms':0,'input_tokens':0,'output_tokens':0,
            'total_tokens':0,'usage_reported':True,'transport_attempts':1}}
    return SimpleNamespace(lead_research_turn=turn,specialist_model_turn=forbidden)


# Test-only substitutions at the provider/telemetry boundary, never runtime ACL.
host.DeepSeekStructuredAgentAdapter.from_config = adapter
host.case_chat_model = forbidden
host.open_approved_data_composition = forbidden
from sec_agent.agent_runtime import user_context, working_memory_tools
from sec_agent.research_foundation import research_library
user_context.user_context_prompt = forbidden
native_memory_scope = working_memory_tools.native_memory_scope
def organization_memory_only(owner, workspace, **options):
    assert owner.startswith('organization:') and options.get('access_check')
    assert options.get('allow_remote_search') is False
    return native_memory_scope(owner, workspace, **options)
working_memory_tools.native_memory_scope = organization_memory_only
research_library.open_library = forbidden
agent_server_entry._require_langsmith_execution_environment = lambda config: None
os.environ['DEEPSEEK_API_KEY'] = 'offline-static-placeholder'
graph = host.research_session_graph
