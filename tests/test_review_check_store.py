"""Incremental inspection and explicit research boundaries, no financial gold."""
import asyncio
from copy import deepcopy
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, messages_to_dict
from mcp import Client
from sec_agent.agent_runtime.case_review_agent import (InspectedCaseReview, build_case_reviewer,
    case_mcp_tools, validate_inspection_checks, CaseReview)
from sec_agent.agent_runtime.review_check_store import merge_checks, restore_checks, restore_findings, inspection_progress
from test_case_review_agent import ScriptedNativeChat, call
from test_review_inspection_recovery import inspected, reads
from test_research_convergence import artifact_fixture
from test_research_mcp import _build_server


def test_large_scope_has_no_contradictory_global_check_count_cap():
    a=artifact_fixture(); payload=inspected(a)
    payload['inspection_checks']*=40
    assert len(InspectedCaseReview.model_validate(payload).inspection_checks)>160


def test_known_limitations_do_not_hide_unfinished_required_checks():
    a=artifact_fixture(); payload=inspected(a)
    payload['research_limitations']=['No public end-user utilization measurements; do not infer deployed usage from issuer revenue.']
    parsed=InspectedCaseReview.model_validate(payload)
    validate_inspection_checks(parsed,a,reads(a),complete=True)
    payload['unresolved_data_requests']=['A required source check has not been performed.']
    with pytest.raises(ValueError,match='completion_must_match'):
        InspectedCaseReview.model_validate(payload)
    payload['unresolved_data_requests']=[]
    payload['inspection_checks']=[]
    with pytest.raises(ValueError,match='inspection_incomplete'):
        validate_inspection_checks(CaseReview.model_validate(payload),a,reads(a),complete=True)


def test_restore_successful_legacy_batches_only_and_replace_same_location():
    a=artifact_fixture();checks=inspected(a)['inspection_checks']; revised=deepcopy(checks[0]);revised['result']='Latest explicit reviewer assessment of this exact version and location.'
    bad=deepcopy(revised);bad['result']='FAILED_DRAFT_MUST_NOT_RESTORE'
    messages=[]
    for identity,rows,status in [('one',checks,'success'),('two',[revised],'success'),('bad',[bad],'error')]:
        messages.extend([AIMessage(content='',tool_calls=[call('submit_case_review',{'review':{'inspection_checks':rows}},identity)]),
            ToolMessage(content='Review handoff accepted for case convergence' if status=='success' else 'Invalid source',status=status,tool_call_id=identity,name='submit_case_review')])
    restored=restore_checks({'messages':messages_to_dict(messages)})
    assert len(restored)==len(merge_checks({},checks))
    assert revised in restored.values() and bad not in restored.values()
    assert all(not r['missing_dimensions'] and not r['missing_claim_ids'] and not r['missing_semantic_target_ids'] for r in inspection_progress(restored,a).values())
    stale=deepcopy(revised);stale['paper_digest']='old-version'
    assert inspection_progress(merge_checks({},[stale]),a)['P01']['saved_checks']==0


def test_native_batch_records_survive_and_close_without_recopied_checks():
    async def exercise():
        a=artifact_fixture(); payload=inspected(a); checks=payload.pop('inspection_checks')
        bad=deepcopy(checks[0]);bad['paper_digest']='stale'
        model=ScriptedNativeChat(marker='batch',replies=[
            [call('read_research_artifact',{'paper_id':p['paper_id']},p['paper_id']) for p in a.catalog()['papers']],
            [call('record_review_checks',{'checks':checks[:2]},'batch1')],
            [call('record_review_checks',{'checks':[bad]},'bad')],
            [call('record_review_checks',{'checks':checks[2:]},'batch2')],
            [call('submit_case_review',{'review':{**payload,'inspection_checks':[]}},'submit')]])
        async with Client(_build_server(case_artifacts=a),raise_exceptions=False) as client:
            graph=build_case_reviewer(role='verifier',model=model,tools=await case_mcp_tools(client),artifacts=a,
                max_model_calls=7,require_inspection=True)
            result=await graph.ainvoke({'messages':[HumanMessage(content='Inspect the synthetic paper in batches.')]})
        assert result['review']['completion']=='complete'
        assert len(result['review']['inspection_checks'])==len(merge_checks({},checks))
        assert any(isinstance(m,ToolMessage) and m.status=='error' and 'stale' in m.content for m in result['messages'])
        assert not any(c['paper_digest']=='stale' for c in result['recorded_inspections'].values())
    asyncio.run(exercise())


def test_prior_submitted_finding_survives_later_delta_but_withdrawal_wins():
    finding={'finding_id':'original','diagnosis':'original saved public finding'}
    messages=[]
    for identity,review in [('one',{'findings':[finding]}),('two',{'findings':[]})]:
        messages.extend([AIMessage(content='',tool_calls=[call('submit_case_review',{'review':review},identity)]),
            ToolMessage(content='Review handoff accepted for case convergence',tool_call_id=identity,name='submit_case_review')])
    saved={'messages':messages_to_dict(messages),'recorded_findings':{}}
    assert restore_findings(saved,{'findings':[]})=={'original':finding}
    assert restore_findings(saved,{'withdrawn_finding_reasons':{'original':'Later original source disproves this prior finding.'}})=={}
