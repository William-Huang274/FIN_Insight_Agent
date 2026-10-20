"""Unified historical business case; scripted decisions, real source tools.

No specialist/reviewer/writer quality claim. A labelled static report consumes
the actual orientation receipts; no fabricated search, SQL, ACL or checkpoint.
"""
import json
import os
from pathlib import Path
import runpy
from types import SimpleNamespace

if os.getenv('FIN_HISTORICAL_DELIVERY_QUALIFICATION') != '1':
    raise RuntimeError('historical_delivery_qualification_only')

fixture = runpy.run_path(str(Path(__file__).with_name('organization_delivery_graph.py')))
host = fixture['host']
from langgraph.config import get_config
from pydantic import TypeAdapter
from sec_agent.agent_runtime.specialist_graph import SpecialistNativeToolBatch
from sec_agent.research_foundation.contracts import canonical_sha256

original_adapter = host.DeepSeekStructuredAgentAdapter.from_config


def adapter(**kwargs):
    original = original_adapter(**kwargs)
    tid = get_config()['configurable']['thread_id']
    step, passages = 0, []
    def turn(request):
        nonlocal step
        if not request.get('orientation_context'):
            return original.lead_research_turn(request)
        step += 1
        spec = json.loads(Path('/probe-historical/case.json').read_text())
        assert request['orientation_context']['source_space'] == 'organization'
        result = json.loads(request['tool_results'][0]['content'])['result'] if step > 1 else None
        if result is not None:
            (Path(os.environ['FIN_PROBE_EVIDENCE'])/f'{tid}-tool-{step-1}.json').write_text(
                json.dumps(result), encoding='utf8')
        search = {'source_space':'organization','operation':'search',
                  'document_id':spec['text_document'], 'query':spec['query']}
        name, args = 'RequestSourceAction', {'action':'request_source','reason_summary':'Historical engineering replay.'}
        if step == 1:
            args['selection'] = {'source_space':'organization','operation':'catalog'}
        elif step == 2:
            assert {r['document_id'] for r in result['items'] if r.get('document_id')} == {spec['text_document'],spec['card_document']}
            args['selection'] = search
        elif step in (3, 4):
            assert result['items']
            item = result['items'][0]
            assert item['organization_source']['resource_id'] == spec['text_resource']
            retrieval = item['retrieval']
            if 'same_receipt_ref' in retrieval:
                retrieval = result['retrieval_contexts'][retrieval['same_receipt_ref']]
            assert retrieval['cache_hit'] is (step == 4)
            assert retrieval['dense_node_ids'] == retrieval['candidate_node_ids'] == [item['node_id']]
            assert not item['writer_citable']
            args['selection'] = search if step == 3 else item['readback']
        elif step == 5:
            passage = next(r for r in result['items'] if r.get('result_state') == 'source_bound_passage')
            assert passage['organization_source']['resource_id'] == spec['text_resource']
            passages.append(passage)
            args['selection'] = {'source_space':'organization','operation':'read','document_id':spec['card_document']}
        elif step == 6:
            passage = next(r for r in result['items'] if r.get('result_state') == 'source_bound_passage')
            assert passage['organization_source']['resource_id'] == spec['card_resource']
            assert spec['metric_record_id'] in passage['passage']
            passages.append(passage)
            name, args = 'SubmitResearchOrientationAction', {
                'reason_summary':'Historical passages read via current organization authority.',
                'disposition':'needs_attention','overview':'Engineering replay only; no financial judgment.',
                'findings':[{'finding_id':f'F{i}','judgment':'Historical source identity was read.',
                    'kind':'observation','read_refs':[f'O{i+3}'],'unresolved':'Financial meaning not assessed.',
                    'evidence_spans':[{'read_ref':f'O{i+3}','passage_id':p['passage_id'],'quote':p['passage'][:600]}]}
                    for i,p in enumerate(passages,1)],
                'topics':[], 'scope_map':[{'question':'Further financial research','status':'needs_discovery',
                    'topic_ids':[],'reason':'Engineering replay only.','revisit_when':'Separate research acceptance.'}],
                'coverage_and_gaps':'No specialist, review or financial quality assessment.',
                'graph_skip_reason':'Only the pinned historical sources are in scope.',
                'recency_skip_reason':'Fixed historical cutoff, not current coverage.'}
        else:
            raise AssertionError('unexpected_historical_script_turn')
        action = TypeAdapter(SpecialistNativeToolBatch).validate_json(json.dumps({
            'action':'native_tool_batch','context_digest':request['context_digest'],
            'tool_calls':[{'id':str(step),'name':name,'args':{'context_digest':request['context_digest'],**args}}]
        })).model_dump(mode='json')
        kwargs['audit_sink']({'event':'outcome','call_id':f'historical:{tid}:{step}',
            'provider_call_attempted':False,'status':'qualification_no_provider','origin':'deterministic_fixture'})
        with (Path(os.environ['FIN_PROBE_EVIDENCE'])/'model-turns.jsonl').open('a') as out:
            out.write(json.dumps({'thread_id':tid,'turn':step,'synthetic':True})+'\n')
        return {'action':action,'runtime_receipt':{'receipt_id':f'historical:{tid}:{step}','kind':'model',
            'actor':request['agent_id'],'status':'success','request_digest':canonical_sha256(request),
            'output_digest':canonical_sha256(action),'elapsed_ms':0,'input_tokens':0,'output_tokens':0,
            'total_tokens':0,'usage_reported':True,'transport_attempts':1}}
    return SimpleNamespace(lead_research_turn=turn, specialist_model_turn=fixture['fixture']['forbidden'])


host.DeepSeekStructuredAgentAdapter.from_config = adapter
graph = host.research_session_graph
