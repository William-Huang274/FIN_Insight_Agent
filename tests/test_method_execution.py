from datetime import date

import pytest

from sec_agent.research_foundation.method_execution import (
    ResearchObligation, EvidencePointer, MethodWorkResult, method_payload,
    assess_result_contract,
)


def fixture():
    task = ResearchObligation(obligation_id="demand", parent_question="增长能否兑现利润",
        question="比较两项业务的收入与利润变化", business_scope="服务器系统",
        as_of=date(2025, 8, 31), method_ids=["financial_quality"],
        required_steps=["F2", "F3"], expectation="conditional", materiality="core",
        source_requirements=["segment table"])
    source = EvidencePointer(source_id="S1", digest="a"*64, locator="p20",
        published_at=date(2025,8,14), observation_period="2025Q2",
        vintage="dated_original", access_state="readable")
    result = MethodWorkResult(obligation_id="demand", execution="completed", summary="有条件比较",
        steps=[dict(step_id=k,status="completed",finding="已比较",source_ids=["S1"]) for k in ["F2","F3"]],
        findings=[dict(statement="增长未必改善利润率",kind="conditional",source_ids=["S1"],
            public_basis="收入和分部利润应同口径比较",assumptions=["业务范围保持可比"],
            alternative="业务组合变化",would_change="分部定义重述")], unresolved=[],
        task_note=dict(changes=["建立比较"],blockers=[],next_action="交Lead评价"))
    return task,source,result


def test_method_content_is_actually_bound_and_hash_changes_on_method_selection():
    task,_,_=fixture()
    payload=method_payload(task)
    assert "OCI重分类" in payload["methods"][0]["content"]
    assert len(payload["method_digests"]["financial_quality"])==64
    task.method_ids=["power_projects"]
    assert "取水" in method_payload(task)["methods"][0]["content"]


@pytest.mark.parametrize("change,code",[
    ({"published_at":date(2025,9,1)},"source_publication_outside_scope"),
    ({"published_at":None},"source_publication_outside_scope"),
    ({"vintage":"current_revised"},"source_vintage_unqualified"),
    ({"access_state":"transport_failed"},"source_not_readable"),
])
def test_bad_evidence_is_not_a_research_fact(change,code):
    task,source,result=fixture()
    source=source.model_copy(update=change)
    errors=assess_result_contract(task,result,{"S1":source})
    assert code in {e["code"] for e in errors}
    assert all(not e["financial_semantics_checked"] for e in errors)


def test_omitted_work_and_wrong_citations_are_precisely_reported():
    task,source,result=fixture()
    result.steps=result.steps[:1]
    result.findings[0].source_ids=["invented"]
    errors=assess_result_contract(task,result,{"S1":source})
    assert {e["code"] for e in errors}=={"missing_required_steps","unknown_source"}
    assert next(e for e in errors if e["code"]=="unknown_source")["location"]=="/findings/0/source_ids"


def test_partial_is_not_silently_promoted_or_fact_globally_downgraded():
    task,source,result=fixture()
    assert assess_result_contract(task,result,{"S1":source})==[]
    result.execution="partial";result.steps[1].status="blocked";result.unresolved=["cost breakdown"]
    assert assess_result_contract(task,result,{"S1":source})==[]
    result.execution="completed"
    assert {e["code"] for e in assess_result_contract(task,result,{"S1":source})}=={"unfinished_step"}


def test_completed_conditional_analysis_may_preserve_unknown_variables():
    task,source,result=fixture()
    result.unresolved=['Customer-specific discounts are unobserved; conclusion is conditional']
    assert assess_result_contract(task,result,{'S1':source})==[]


def test_unknown_method_is_rejected_before_dispatch():
    task,_,_=fixture()
    with pytest.raises(ValueError,match="unknown_method_id"):
        ResearchObligation.model_validate({**task.model_dump(),"method_ids":["invented"]})
