"""Deterministic source navigation/compatibility; no financial gold verdict."""
from copy import deepcopy
import asyncio
import json
import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from sec_agent.agent_runtime.evidence_resolution import (
    resolve_quote, citation_inventory, confirmed_reference, delivery_reference_findings, read_source_span)
from sec_agent.agent_runtime.case_review_agent import (
    CaseReview, validate_case_review, validate_inspection_checks, build_case_reviewer, case_mcp_tools)
from sec_agent.agent_runtime.review_inspection import inspection_manifest
from test_research_convergence import artifact_fixture
from test_review_inspection_recovery import inspected, reads
from test_case_review_agent import review_fixture, ScriptedNativeChat, call
from test_research_mcp import _build_server
from mcp import Client


def sample():
    a=artifact_fixture()
    a._sources['P01:S002']={'result_state':'source_bound_passage','passage_id':'PASSAGE::CHUNK::docA:2:3::hashA',
        'document_id':'docA','node_id':'CHUNK::docA:2:3','content_sha256':'hashA',
        'passage':'Income |  | 10 |  | 20 |\nTax |  | (2) |  | (4) |\n'}
    a._papers['P01']['workpaper']['narrative_markdown']='Growth contribution requires checking. PASSAGE::...2:3'
    return a


def test_table_compatibility_restores_only_unique_identical_nonempty_cells():
    body='Income |  | 10 |  | 20 |\nTax |  | (2) |  | (4) |\n'
    request='Income | 10 | 20 |\nTax | (2) | (4) |'
    exact, record=resolve_quote(body,request)
    assert exact==body.rstrip() and record['origin']=='runtime_compatibility_parse'
    assert record['original_input']==request and record['normalized_result']==exact
    assert not record['financial_semantics_verified']
    for wrong in (request.replace('(4)','4'),request.replace('20','21'),request.replace('Tax','Revenue')):
        assert resolve_quote(body,wrong)==(wrong,None)
    assert resolve_quote(body+body,request)==(request,None)


def test_candidate_confirmation_requires_read_and_never_repairs_draft_silently():
    a=sample(); row=citation_inventory(a,'P01')[0]
    assert row['status']=='candidate_requires_confirmation'
    assert row['candidates'][0]['source_id']=='P01:S002'
    assert row['runtime_parsing']['normalized_result'] is None
    with pytest.raises(ValueError,match='requires_actual_current_source_read'):
        confirmed_reference(a,'P01',row['reference_id'],'P01:S002','Actual source identity and content checked.',[])
    messages=[ToolMessage(name='read_research_source',tool_call_id='read',content='source',artifact=a.read_source('P01:S002'))]
    confirmed=confirmed_reference(a,'P01',row['reference_id'],'P01:S002','Actual source identity and content checked.',messages)
    assert confirmed['delivery_reference_needs_repair'] and confirmed['read_tool_call_ids']==['read']
    messages.append(ToolMessage(name='confirm_review_reference',tool_call_id='confirm',content='confirmed',artifact=confirmed))
    findings,records=delivery_reference_findings(a,messages,complete=True)
    assert len(findings)==1 and records[0]['origin']=='runtime_compatibility_parse'
    assert 'PASSAGE::...2:3' in a.read_paper('P01')['narrative_markdown']
    a._papers['P01']['workpaper']['narrative_markdown']+=' Revision.'
    with pytest.raises(ValueError,match='unconfirmed_references'):
        delivery_reference_findings(a,messages,complete=True)


def test_same_suffix_in_distinct_documents_is_ambiguous_and_cannot_autoconfirm():
    a=sample();a._sources['P01:S003']=dict(a._sources['P01:S002'],passage_id='PASSAGE::CHUNK::docB:2:3::hashB',
        document_id='docB',node_id='CHUNK::docB:2:3',content_sha256='hashB')
    a._papers['P01']['sources']['P01:S003']={}
    row=citation_inventory(a,'P01')[0]
    assert row['status']=='ambiguous' and len(row['candidates'])==2
    with pytest.raises(ValueError,match='unconfirmed_references'):
        delivery_reference_findings(a,[],complete=True)
    a._papers['P01']['workpaper']['narrative_markdown']='PASSAGE::CHUNK::docA:2:3::hashA'
    assert citation_inventory(a,'P01')[0]['status']=='exact'


def test_digest_bound_quote_selection_and_compatibility_receipts():
    a=sample();body=a._sources['P01:S002']['passage']; selected=read_source_span(a,'P01:S002',0,len(body)-1)
    review=CaseReview.model_validate(review_fixture(a))
    finding={'finding_id':'F','paper_id':'P01','severity':'advisory','problematic_quote':'Growth contribution',
        'diagnosis':'Synthetic source operation test only.','requested_change':'Inspect the actual selected source span.',
        'source_checks':[{'source_id':'P01:S002','quote_span':selected['quote_span']}]}
    review=review.model_copy(update={'findings':CaseReview.model_validate({**review.model_dump(),'findings':[finding]}).findings})
    receipts=[];validate_case_review(review,a,reads(a),parsing_records=receipts)
    assert review.findings[0].source_checks[0].quote==body.rstrip()
    assert receipts[0]['source_check_index']==0 and receipts[0]['origin']=='runtime_compatibility_parse'
    review.findings[0].source_checks[0].quote_span.source_digest='stale'
    with pytest.raises(ValueError,match='stale_digest'):
        validate_case_review(review,a,reads(a))


def test_literal_anchor_selection_needs_no_model_character_count_and_rejects_ambiguity():
    a=sample()
    selected=read_source_span(a,'P01:S002',anchor='Tax',max_characters=100)
    assert selected['text']=='Tax |  | (2) |  | (4) |\n'
    assert selected['quote_span']['start']==len('Income |  | 10 |  | 20 |\n')
    assert selected['runtime_parsing']['method']=='exact_source_anchor_v1'
    with pytest.raises(ValueError,match='not_unique'):
        read_source_span(a,'P01:S002',anchor='|')


def test_overall_equation_cannot_cover_other_paragraphs_or_ambiguous_wording():
    a=artifact_fixture();good=CaseReview.model_validate(inspected(a))
    validate_inspection_checks(good,a,reads(a),complete=True)
    checks=[c for c in good.inspection_checks if c.dimension=='prose_consistency']
    good.inspection_checks.remove(checks[-1])
    with pytest.raises(ValueError,match='semantic_paragraphs_unchecked'):
        validate_inspection_checks(good,a,reads(a),complete=True)
    good=CaseReview.model_validate(inspected(a));check=next(c for c in good.inspection_checks if c.dimension=='prose_consistency')
    check.financial_verdict='contradicted'
    with pytest.raises(ValueError,match='semantic_verdict_status_mismatch'):
        validate_inspection_checks(good,a,reads(a),complete=True)


def test_native_record_tool_persists_runtime_origin_separately_from_raw_model_call():
    async def run():
        a=sample()
        finding={'finding_id':'F','paper_id':'P01','severity':'advisory','problematic_quote':'Growth contribution',
            'diagnosis':'Synthetic compatibility operation only.','requested_change':'Inspect original table headings and periods.',
            'source_checks':[{'source_id':'P01:S002','quote':'Income | 10 | 20 |'}]}
        model=ScriptedNativeChat(marker='synthetic',replies=[
            [call('read_research_artifact',{'paper_id':'P01','section':'workpaper'},'read')],
            [call('record_case_finding',{'finding':finding},'record')]])
        async with Client(_build_server(case_artifacts=a)) as client:
            agent=build_case_reviewer(role='counter',model=model,tools=await case_mcp_tools(client),artifacts=a,max_model_calls=2)
            result=await agent.ainvoke({'messages':[HumanMessage(content='Synthetic proof, not a financial verdict.')]})
        actual=result['recorded_findings']['F']['source_checks'][0]['quote']
        assert actual=='Income |  | 10 |  | 20 |'
        saved=next(m for m in result['messages'] if isinstance(m,ToolMessage) and m.name=='record_case_finding')
        assert saved.artifact['runtime_parsing'][0]['origin']=='runtime_compatibility_parse'
        assert finding['source_checks'][0]['quote']=='Income | 10 | 20 |'
    asyncio.run(run())


def test_concise_semantic_result_keeps_evidence_and_relationship_checks():
    a=artifact_fixture();payload=inspected(a)
    for check in payload['inspection_checks']:
        check['result']='一致'
    review=CaseReview.model_validate(payload)
    validate_inspection_checks(review,a,reads(a),complete=True)
    payload['inspection_checks'][0]['result']='  '
    with pytest.raises(ValueError,match='must_not_be_blank'):
        CaseReview.model_validate(payload)
    prose=next(c for c in review.inspection_checks if c.dimension=='prose_consistency')
    prose.supported_relationship=''
    with pytest.raises(ValueError,match='semantic_relationship_comparison_required'):
        validate_inspection_checks(review,a,reads(a),complete=True)


def test_native_schema_feedback_keeps_paths_without_echoing_full_model_arguments():
    async def run():
        a=sample()
        finding={'finding_id':'F','paper_id':'P01','severity':'invalid-severity',
            'problematic_quote':'Growth contribution','diagnosis':'UNIQUE_RAW_PAYLOAD_'+('x'*20000),
            'requested_change':'Inspect original source only.'}
        model=ScriptedNativeChat(marker='synthetic',replies=[
            [call('read_research_artifact',{'paper_id':'P01','section':'workpaper'},'read')],
            [call('record_case_finding',{'finding':finding},'bad')]])
        async with Client(_build_server(case_artifacts=a)) as client:
            agent=build_case_reviewer(role='counter',model=model,tools=await case_mcp_tools(client),artifacts=a,max_model_calls=2)
            result=await agent.ainvoke({'messages':[HumanMessage(content='Synthetic schema failure only.')]})
        feedback=next(m for m in result['messages'] if isinstance(m,ToolMessage) and m.tool_call_id=='bad')
        assert feedback.status=='error' and len(feedback.content)<2000
        assert 'finding.severity' in feedback.content and 'finding.diagnosis' in feedback.content
        assert 'UNIQUE_RAW_PAYLOAD_' not in feedback.content
        assert feedback.artifact['runtime_parsing'][0]['origin']=='runtime_compatibility_parse'
        assert not result.get('recorded_findings') and not result.get('review')
        original=next(m for m in result['messages'] if getattr(m,'tool_calls',[]) and m.tool_calls[0]['id']=='bad')
        assert original.tool_calls[0]['args']['finding']==finding
    asyncio.run(run())
