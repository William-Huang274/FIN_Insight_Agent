import asyncio
from copy import deepcopy
import json

import pytest

from sec_agent.research_foundation.method_submission import (
    decode_submission, target_directory, source_directory, compact_schema, amend_candidate, SubmissionRejected)
from sec_agent.research_foundation.method_diagnostic_graph import compile_method_probe, SubmittedProbeDecision
from sec_agent.research_foundation.method_execution import MethodWorkResult
from sec_agent.research_foundation.method_review import review_context
from test_method_review import output, full_review, decision, task
from test_method_diagnostic_graph import make_snapshot


def test_selected_source_binds_whole_window_without_inferring_claim_support():
    from sec_agent.research_foundation.method_review import assess_method_review
    row=output();value=decision('stop',review=full_review(row))
    sources=source_directory({'review_evidence':row['review_evidence']})
    ref=next(iter(sources))
    for check in value['review']['inspection_checks']:
        check['source_checks']=[{'source_ref':ref}]
    before=deepcopy(value)
    parsed,receipt=decode_submission(value,SubmittedProbeDecision,sources=sources)
    assert value==before
    source=parsed.review.inspection_checks[0].source_checks[0]
    assert source.quote=='' and source.quote_span.end==len(row['review_evidence'][0]['body'])
    assert source.quote_span.source_digest==row['review_evidence'][0]['digest']
    assert not assess_method_review([row],parsed.review)['errors']
    assert all(r['method']=='current_delivered_source_window_v1' and not r['financial_semantics_verified']
               for r in receipt['runtime_parsing'])
    for conflict in ({'source_ref':'E-stale'}, {'source_ref':ref,'source_id':'another'}):
        value['review']['inspection_checks'][0]['source_checks']=[conflict]
        with pytest.raises(SubmissionRejected):decode_submission(value,SubmittedProbeDecision,sources=sources)
    row['review_evidence'][0]['body']+=' changed'
    assert ref not in source_directory({'review_evidence':row['review_evidence']})


def test_rejected_quote_has_precise_supplement_path_and_still_requires_review():
    from sec_agent.research_foundation.method_review import assess_method_review
    from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
    row=output();value=decision('stop',review=full_review(row))
    value['review']['inspection_checks'][0]['source_checks'][0]['quote']='invented ... text'
    parsed,_=decode_submission(value,SubmittedProbeDecision)
    receipt=assess_method_review([row],parsed.review)
    assert receipt['errors'] and receipt['state']['checks']=={}
    errors=receipt['submission_errors']
    assert errors[0]['location']=='/review/inspection_checks/0/source_checks/0'
    sources=source_directory({'review_evidence':row['review_evidence']})
    candidate,audit=amend_candidate({'candidate':value,'candidate_digest':canonical_sha256(value),'errors':errors},
        canonical_sha256(value),{errors[0]['location']:{'source_ref':next(iter(sources))}})
    updated,_=decode_submission(candidate,SubmittedProbeDecision,sources=sources)
    assert not assess_method_review([row],updated.review)['errors']
    assert updated.synthesis==parsed.synthesis and audit['basis']['requires_full_revalidation']


def test_compact_binding_preserves_verdict_and_raw_input():
    row=output();value=decision('stop',review=full_review(row))
    directory=target_directory({'review_context':review_context([row])})
    for check,ref in zip(value['review']['inspection_checks'],directory):
        for key in ('paper_id','paper_digest','field_path','target_quote'): check.pop(key)
        check['target_ref']=ref
    compact_schema(SubmittedProbeDecision).model_validate(value)
    original=deepcopy(value)
    parsed,receipt=decode_submission(value,SubmittedProbeDecision,directory)
    assert value==original
    assert parsed.review.inspection_checks[0].paper_digest==next(iter(directory.values()))['paper_digest']
    assert parsed.review.inspection_checks[0].financial_verdict=='supported'
    assert len(receipt['runtime_parsing'])==2
    assert all(r['origin']=='runtime_compatibility_parse' for r in receipt['runtime_parsing'])
    fields=compact_schema(SubmittedProbeDecision).model_json_schema()['$defs']['CompactMethodInspection']['properties']
    assert 'target_ref' in fields and 'paper_digest' not in fields and 'financial_verdict' in fields


@pytest.mark.parametrize('fault',['stale','conflict'])
def test_navigation_never_silently_overrides_explicit_wrong_identity(fault):
    row=output();value=decision('stop',review=full_review(row));directory=target_directory({'review_context':review_context([row])})
    c=value['review']['inspection_checks'][0];c['target_ref']=next(iter(directory))
    if fault=='stale': directory={}
    else: c['paper_digest']='wrong'
    with pytest.raises(SubmissionRejected) as exc:decode_submission(value,SubmittedProbeDecision,directory)
    assert not exc.value.receipt['executed'] and not exc.value.receipt['automatic_retry']
    assert exc.value.receipt['raw_response']==value


def test_whole_json_fence_accepted_without_changing_research():
    value=output()['result'];raw='```json\n'+json.dumps(value)+'\n```'
    parsed,receipt=decode_submission(raw,MethodWorkResult)
    assert parsed.summary==value['summary']
    assert receipt['runtime_parsing'][0]['method']=='complete_outer_json_fence_v1'


@pytest.mark.parametrize('raw',['{"summary":"one","summary":"two"}', '{"a":NaN}',
    '{"summary":"truncated', 'prefix {"a":1}', '{} {}','[]'])
def test_ambiguous_or_incomplete_json_is_saved_not_completed(raw):
    with pytest.raises(SubmissionRejected) as exc:decode_submission(raw,MethodWorkResult)
    assert exc.value.receipt['raw_response']==raw and exc.value.receipt['candidate'] is None


def test_schema_failure_can_be_supplemented_only_at_error_with_same_version():
    value=output()['result'];value['task_note'].pop('next_action')
    with pytest.raises(SubmissionRejected) as exc:decode_submission(value,MethodWorkResult)
    receipt=exc.value.receipt
    assert receipt['errors'][0]['location']=='/task_note/next_action'
    candidate,record=amend_candidate(receipt,receipt['candidate_digest'],{'/task_note/next_action':'Lead review'})
    parsed,_=decode_submission(candidate,MethodWorkResult)
    assert parsed.summary==value['summary'] and record['basis']['requires_full_revalidation']
    assert 'next_action' not in receipt['candidate']['task_note']
    with pytest.raises(ValueError,match='explicit_error_fields'):
        amend_candidate(receipt,receipt['candidate_digest'],{'/summary':'changed research'})
    with pytest.raises(ValueError,match='stale'):
        amend_candidate(receipt,'other',{'/task_note/next_action':'Lead review'})


def test_fanout_preserves_valid_sibling_and_rejected_candidate_without_retry(tmp_path):
    calls=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        if actor=='lead':return decision('delegate',[task('good'),task('bad')])
        result=output(actor)['result']
        if actor=='bad':result['task_note'].pop('next_action')
        return result
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda *a:None,runtime_handoffs=True)
    state=asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],results=[],waves=0)))
    assert sorted(calls)==['bad','good','lead']
    assert state['terminal']=='submission_format_unresolved'
    assert [r['obligation']['obligation_id'] for r in state['results']]==['good']
    assert state['submission_failures'][0]['candidate']['obligation_id']=='bad'


def test_bad_lead_format_is_checkpoint_state_not_dispatch(tmp_path):
    from langgraph.checkpoint.memory import InMemorySaver
    calls=[]
    async def call(actor,payload,schema):
        calls.append(actor);return '{"action":"delegate"'
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda *a:None,
        runtime_handoffs=True,checkpointer=InMemorySaver())
    config={'configurable':{'thread_id':'format'}}
    state=asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],results=[],waves=0),config))
    saved=asyncio.run(graph.aget_state(config))
    assert calls==['lead'] and saved.values['submission_failures']==state['submission_failures']
    assert state['terminal']=='submission_format_unresolved'


def test_calculator_observation_survives_later_submission_failure():
    from sec_agent.research_foundation.method_worker import compile_method_worker
    calls=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        if not payload['tool_observations']:
            return dict(action='calculate',result=None,calculations=[dict(expression='a-b',operands={
                'a':dict(source_id='P1',literal='120',quote='Current 120 prior 100'),
                'b':dict(source_id='P1',literal='100',quote='Current 120 prior 100')},
                result_unit='USD million',rationale='Current minus prior')])
        return '{"action":"finish"'
    payload=dict(instructions='Method',read_results=[dict(status='readable',source=dict(url='https://example.com'),
        items=[dict(id='P1',body='Current 120 prior 100',digest='a'*64,locator='paragraph1')])])
    graph=compile_method_worker(call=call,actor='task',payload=payload,record=lambda *a:None,runtime_submissions=True)
    state=asyncio.run(graph.ainvoke(dict(tool_rounds=0,observations=[])))
    assert calls==['task','task'] and len(state['observations'])==1
    failure=state['submission_failure']
    assert failure['tool_observations'][0]['result']['value_decimal']=='20'
    assert failure['raw_response']=='{"action":"finish"' and not failure['automatic_retry']
