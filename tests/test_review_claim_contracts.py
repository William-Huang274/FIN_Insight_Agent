"""Delivery clarity and complete saved-calculation bindings, not financial gold."""
import asyncio
from copy import deepcopy
import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from mcp import Client
from sec_agent.agent_runtime.case_review_agent import (CaseReview, FindingConfirmation, validate_inspection_checks,
    validate_finding_confirmation, build_case_reviewer, case_mcp_tools)
from sec_agent.agent_runtime.review_claim_contracts import calculation_lineage
from sec_agent.agent_runtime.research_session import responsible_author_feedback
from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources
from test_review_inspection_recovery import inspected, reads
from test_research_convergence import artifact_fixture
from test_case_review_agent import ScriptedNativeChat, call
from test_research_mcp import _build_server


def clarity_review(a):
    review=CaseReview.model_validate(inspected(a))
    check=next(c for c in review.inspection_checks if c.dimension=='prose_consistency')
    check.clarity_verdict='needs_clarification'
    check.clarity_reason='The conclusion is supported but the wording leaves the comparison scope implicit.'
    check.clarification='State the comparison scope explicitly in this paragraph, preserving the supported conclusion.'
    return review,check


def test_supported_finance_still_generates_required_local_clarification_and_routes_to_author():
    a=artifact_fixture();review,check=clarity_review(a);receipts=[]
    validate_inspection_checks(review,a,reads(a),complete=True,parsing_records=receipts)
    assert check.financial_verdict=='supported' and check.status=='issue'
    assert len(review.findings)==1 and review.findings[0].finding_type=='clarification'
    assert review.findings[0].problematic_quote==check.target_quote
    assert receipts[-1]['origin']=='runtime_compatibility_parse'
    feedback=responsible_author_feedback({r:{'status':'review_submitted','review':review.model_dump()} for r in ('counter','verifier')},a)
    assert all(f['finding_type']=='clarification' for f in feedback[check.paper_id])
    # Preparing again is idempotent for findings; it never closes the declared issue.
    validate_inspection_checks(review,a,reads(a),complete=True)
    assert len(review.findings)==1


def test_legacy_read_is_compatible_but_new_review_requires_both_axes_and_calculation_scope():
    a=artifact_fixture();payload=inspected(a)
    for c in payload['inspection_checks']:
        c.pop('financial_verdict',None);c.pop('clarity_verdict',None);c.pop('calculation_check',None)
    review=CaseReview.model_validate(payload)
    with pytest.raises(ValueError,match='separate_financial_and_clarity_assessments_required'):
        validate_inspection_checks(review,a,reads(a),complete=True)


@pytest.mark.parametrize('unresolved', ['financial', 'calculation'])
def test_unresolved_work_preserves_actionable_clarification_without_forcing_completion(unresolved):
    a=artifact_fixture();review,check=clarity_review(a)
    if unresolved == 'financial':
        check.financial_verdict='insufficient'
    else:
        check.calculation_check='unresolved'
    check.status='unresolved'
    review.unresolved_data_requests=['Check additional evidence before deciding financial support.']
    validate_inspection_checks(review,a,reads(a),complete=False)
    assert check.status=='unresolved' and review.findings[0].finding_type=='clarification'


def test_explicit_semantic_target_cannot_be_skipped_with_supported_clear_labels():
    a=artifact_fixture();review=CaseReview.model_validate(inspected(a))
    next(c for c in review.inspection_checks if c.dimension=='prose_consistency').status='not_applicable'
    with pytest.raises(ValueError,match='semantic_verdict_status_mismatch'):
        validate_inspection_checks(review,a,reads(a),complete=True)


def test_clarification_cannot_close_on_financial_support_without_current_wording():
    a=artifact_fixture();review,check=clarity_review(a)
    validate_inspection_checks(review,a,reads(a),complete=True)
    f=review.findings[0].model_dump();confirmation={'findings_to_confirm':{'counter':[f]}}
    review.finding_checks=[FindingConfirmation(
        finding_id=f['finding_id'],status='resolved',reason='The central financial conclusion remains supported.')]
    with pytest.raises(ValueError,match='clarification_closure_requires_current_clear_wording'):
        validate_finding_confirmation(review,confirmation,a)
    review.finding_checks[0].clarity_verdict='clear';review.finding_checks[0].current_quote=check.target_quote
    validate_finding_confirmation(review,confirmation,a)  # Assertion is traceable, not proven true by runtime.


def calculation_fixture(a):
    for sid,text in [('P01:S090','Segment income 100 million for the quarter.'),('P01:S091','Group revenue 800 million for the quarter.')]:
        a._sources[sid]={'result_state':'source_bound_passage','writer_citable':True,'passage_id':'PASSAGE::'+sid,'passage':text}
    request=SourceBoundCalculation(expression='a/b*100',result_unit='percent',rationale='Same-quarter segment income divided by group revenue.',
        operands={'a':{'source_id':'P01:S090','literal':'100','quote':a._sources['P01:S090']['passage']},
                  'b':{'source_id':'P01:S091','literal':'800','quote':a._sources['P01:S091']['passage']}})
    value=calculate_from_sources(request,a.source_item)
    message=ToolMessage(name='calculate_research_metric',tool_call_id='calc',content='Saved calculation',artifact=value)
    return value,message


def test_runtime_expands_missing_denominator_binding_from_actual_calculator_receipt():
    a=artifact_fixture();calc,message=calculation_fixture(a)
    review=CaseReview.model_validate(inspected(a));check=review.inspection_checks[0]
    check.result='New comparison: 100 / 800 * 100 = 12.5 percent.'
    check.calculation_check='bound';check.calculation_ids=[calc['calculation_id']]
    before=check.model_dump();receipts=[]
    validate_inspection_checks(review,a,[*reads(a),message],complete=True,parsing_records=receipts)
    assert {'P01:S090','P01:S091'}.issubset({s.source_id for s in check.source_checks})
    receipt=next(r for r in receipts if r['method']=='review_calculation_lineage_v1')
    assert receipt['original_input']['source_checks']==before['source_checks']
    assert not receipt['financial_semantics_verified']
    assert receipt['normalized_result']['calculations'][0]['value_decimal']=='12.500'
    # A copied/fabricated ID without an observed or stored receipt cannot be accepted.
    with pytest.raises(ValueError,match='calculation_binding_unavailable'):
        validate_inspection_checks(CaseReview.model_validate({**review.model_dump(),'inspection_checks':[before,*[c.model_dump() for c in review.inspection_checks[1:]]]}),a,reads(a),complete=True)


def test_undeclared_numeric_formula_cannot_hide_behind_valid_single_source():
    a=artifact_fixture();review=CaseReview.model_validate(inspected(a))
    review.inspection_checks[0].result='Derived ratio: 100 / 800 = 0.125.'
    with pytest.raises(ValueError,match='calculation_declaration_conflicts'):
        validate_inspection_checks(review,a,reads(a),complete=True)


def test_arithmetic_navigation_does_not_treat_date_or_period_comparison_as_a_formula():
    from sec_agent.agent_runtime.review_claim_contracts import arithmetic_hint
    assert not arithmetic_hint('Comparison for 2025/2024, published 2025/03/31.')
    assert arithmetic_hint('11,547 / 155,667 = 0.074')


def test_nested_calculation_lineage_keeps_all_leaf_sources_and_explicit_assumptions():
    a=artifact_fixture();first,message=calculation_fixture(a)
    a._sources[first['calculation_id']]=first
    second=calculate_from_sources(SourceBoundCalculation(expression='prior*factor',result_unit='scenario percent',
        rationale='Illustrative assumed factor, not disclosed fact.',operands={
            'prior':{'source_id':first['calculation_id']},'factor':{'literal':'2','assumption_note':'Hypothetical scale'}}),a.source_item)
    a._sources[second['calculation_id']]=second
    lineage=calculation_lineage(a,[],second['calculation_id'])
    assert len(lineage['source_checks'])==2 and len(lineage['calculations'])==2
    assert lineage['assumptions'][0]['authority']=='assumption'
    a._sources['P01:S091']['passage']='Changed source no longer contains the operand.'
    with pytest.raises(ValueError,match='unavailable_or_changed'):
        calculation_lineage(a,[],second['calculation_id'])


def test_native_submit_preserves_raw_output_and_returns_generated_clarification():
    async def run():
        a=artifact_fixture();review,check=clarity_review(a);payload=review.model_dump()
        model=ScriptedNativeChat(marker='synthetic',replies=[
            [call('read_research_artifact',{'paper_id':pid,'section':'workpaper'},'read-'+pid) for pid in ('P01','P02')],
            [call('submit_case_review',{'review':payload},'submit')]])
        async with Client(_build_server(case_artifacts=a)) as client:
            agent=build_case_reviewer(role='counter',model=model,tools=await case_mcp_tools(client),artifacts=a,max_model_calls=3,require_inspection=True)
            result=await agent.ainvoke({'messages':[HumanMessage(content='Synthetic plumbing qualification only.')]})
        assert result['review']['findings'][0]['finding_type']=='clarification'
        assert result['runtime_parsing'][-1]['method']=='review_clarification_handoff_v1'
        original=next(m for m in result['messages'] if getattr(m,'tool_calls',[]) and m.tool_calls[0]['id']=='submit')
        assert original.tool_calls[0]['args']['review']['findings']==[]
        assert original.tool_calls[0]['args']['review']['inspection_checks'][1]['status']=='checked'
    asyncio.run(run())
