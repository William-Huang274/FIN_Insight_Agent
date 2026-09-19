import asyncio
from copy import deepcopy

import pytest

from sec_agent.research_foundation.specialist_delegation import (
    compile_specialist_delegation, factor_judgments, expand_judgments)
from sec_agent.research_foundation.method_handoffs import judgment_directory


READS=[{'status':'readable','source':{'url':'https://example.test/survey'},'items':[
    {'id':'P1','body':'Adults surveyed in January; reported use is 20%.','digest':'a'*64,'locator':'page 1'}]}]


def paper(summary='Original'):
    return {'obligation_id':'survey-delegated','execution':'completed','summary':summary,
        'steps':[{'step_id':s,'status':'completed','finding':'Adults in January; descriptive only.',
                  'source_ids':['P1']} for s in ['S1','S2','S3','S4']],
        'findings':[{'statement':summary+' adults report use in January.', 'kind':'factual',
            'source_ids':['P1'],'public_basis':'Original survey, not measured revenue.',
            'assumptions':[], 'basis_step_ids':['S1','S4']}],
        'unresolved':[], 'task_note':{'changes':[],'blockers':[],'next_action':'Upstream review'}}


def decision(payload, action='accept', **extra):
    return {'action':action,'paper_digest':payload['delivery']['paper_digest'],
        'checks':[{'judgment_ref':ref,'disposition':'needs_repair' if action=='return' else 'usable',
                   'reason':'Check in assigned context'} for ref in payload['delivery']['judgments']],
        'accepted_use':'Survey observation only','issues':['Verify linked statements'] if action=='return' else [],**extra}


def test_real_nodes_keep_roles_separate_through_inspection_and_return():
    seen=[];events=[]; review_calls=0; worker_calls=0
    async def call(actor,payload,schema):
        nonlocal review_calls,worker_calls
        seen.append((actor,deepcopy(payload)))
        if actor=='lead-plan':
            assert 'read_results' not in payload
            return {'question':'Check adoption evidence','purpose':'Inform research',
                    'success_criteria':['Keep population and time']}
        if actor=='survey-specialist':
            worker_calls+=1
            assert list(payload['method_digests'])==['survey_analysis']
            assert 'delivery' not in payload and 'judgments' not in payload
            if worker_calls==1:
                assert 'current_workpaper' not in payload
            else:
                assert payload['current_workpaper']['summary']=='Original'
                assert payload['return_issues']==['Verify linked statements']
                assert payload['remaining_calculation_rounds']==3
            return {'action':'finish','result':paper('Revised' if worker_calls==2 else 'Original')}
        review_calls+=1
        assert 'methods' not in payload and 'read_results' not in payload
        assert 'original_workpaper' not in payload and 'worker_result' not in payload
        assert all('body' not in s for s in payload['delivery']['source_catalog'])
        if review_calls==1:
            assert payload['evidence_access']['original_passage_ids_in_this_request']==[]
            assert not payload['evidence_access']['author_basis_is_original_evidence']
            return decision(payload,'inspect',evidence_requests=['P1'])
        if review_calls==2:
            assert payload['requested_evidence']==READS[0]['items']
            assert payload['evidence_access']['original_passage_ids_in_this_request']==['P1']
            return decision(payload,'return')
        assert payload['requested_evidence']==[]
        assert payload['delivery']['summary']=='Revised'
        return decision(payload)
    graph=compile_specialist_delegation(question='Broad question',as_of='2026-09-19',reads=READS,
        call=call,record=lambda e,v:events.append((e,v)))
    result=asyncio.run(graph.ainvoke({}))
    assert result['terminal']=='lead_accepted_pending_host_semantic_review'
    assert worker_calls==2 and review_calls==3
    handoffs=[p for e,p in events if e=='role_handoff']
    assert handoffs[0]['paper_digest']!=handoffs[1]['paper_digest']
    assert all(not p['financial_semantics_checked_by_runtime'] for p in handoffs)


@pytest.mark.parametrize('fault,terminal',[
    ('stale','review_identity_failure'),('unchecked','review_incomplete_acceptance'),
    ('unknown_evidence','unknown_or_duplicate_evidence_request'),('return_limit','repair_limit')])
def test_invalid_review_never_becomes_acceptance(fault,terminal):
    async def call(actor,payload,schema):
        if actor=='lead-plan':
            return {'question':'Check survey','purpose':'Research','success_criteria':['Evidence']}
        if actor=='survey-specialist':return {'action':'finish','result':paper()}
        result=decision(payload)
        if fault=='stale':result['paper_digest']='0'*64
        if fault=='unchecked':result['checks']=[]
        if fault=='unknown_evidence':result=decision(payload,'inspect',evidence_requests=['UNKNOWN'])
        if fault=='return_limit':result=decision(payload,'return')
        return result
    result=asyncio.run(compile_specialist_delegation(question='q',as_of='2026-09-19',reads=READS,
        call=call,record=lambda *args:None,max_repairs=0).ainvoke({}))
    assert result['terminal']==terminal


def test_existing_candidate_is_reviewed_without_rerun_or_silent_contract_repair():
    original=paper()
    original['task_note']['execution_receipt_refs']=['CALC::not-an-execution-receipt']
    seen=[]
    async def call(actor,payload,schema):
        seen.append(actor)
        assert actor=='lead-review'
        assert payload['delivery']['contract_errors'][0]['code']=='unknown_execution_receipt'
        return decision(payload)
    result=asyncio.run(compile_specialist_delegation(question='q',as_of='2026-09-19',reads=READS,
        call=call,record=lambda *args:None,initial_assignment={'question':'q','purpose':'p','success_criteria':['c']},
        initial_worker_result={'action':{'action':'finish','result':original},'observations':[]}).ainvoke({}))
    assert seen==['lead-review']
    assert result['terminal']=='review_incomplete_acceptance'
    assert result['worker_result']['action']['result']==original


def test_handoff_dedup_is_lossless_with_conditions_and_legacy_step_links():
    result=paper()
    result['findings'].append({**deepcopy(result['findings'][0]),
        'statement':'Conditional population comparison only.',
        'assumptions':['Same target population; different questionnaire forms.'],
        'basis_step_ids':[]})
    obligation={'obligation_id':'survey-delegated','as_of':'2026-09-19','question':'Assigned scope'}
    directory=judgment_directory([{'obligation':obligation,'result':result,'review_evidence':READS[0]['items']}])
    original=deepcopy(directory)
    judgments,tables=factor_judgments(directory)
    assert expand_judgments(judgments,tables)==original
    assert directory==original
    assert len(tables['scopes'])==1 and len(tables['steps'])==4
    assert len(tables['sources'])==1
    assert len(list(judgments.values())[1]['basis_step_refs'])==4
    judgments[next(iter(judgments))]['finding']['statement']='Caller changed copy'
    assert directory==original
