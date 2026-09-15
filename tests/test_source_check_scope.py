import json
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from sec_agent.agent_runtime.source_check_scope import RequiredSourceCheck, source_check_progress, source_check_errors
from sec_agent.agent_runtime.task_outcome import AuthorTaskNote
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
from test_specialist_graph import _input, _ToolPorts, _ScriptedModel, _evidence_action, _finance_action, _submission
from test_specialist_tool_batch import _handoff


def scope():
    return {"criterion":"Inspect the whole income statement and its two-period headings",
        "selection":{"source_space":"uploads","operation":"read","document_id":"UPLOAD::fixture","node_id":"CHUNK::fixture:1"},
        "required_source_ids":["PASSAGE::fixture:full"],"inspect":["Operating expenses","Non-operating income","Tax and net income","Unit, period and footnotes"]}


def test_scope_requires_a_read_not_search_preview():
    value=scope();value["selection"]={"source_space":"uploads","operation":"search","query":"income"}
    with pytest.raises(ValidationError,match="required_source_check_needs_original_read"):
        RequiredSourceCheck.model_validate(value)


@pytest.mark.parametrize("status,reference",[("empty","PASSAGE::fixture:full"),("tool_failure","PASSAGE::fixture:full"),("success","PASSAGE::fixture:short")])
def test_failed_or_different_window_never_completes_required_read(status,reference):
    note=AuthorTaskNote(summary="Author says completed",coverage=[{"criterion":scope()["criterion"],"status":"completed",
        "explanation":"Claimed completion is not actual source access.","fields":["counterevidence"]}])
    errors=source_check_errors([scope()],{"observations":[{"status":status,"references":[{"ref_id":reference,"writer_citable":True,"authority_state":"source_bound_passage"}]}]},SimpleNamespace(task_note=note))
    assert any(e.startswith("required_source_read_missing") for e in errors)


def test_actual_read_still_requires_explicit_assessment_and_output_location():
    notebook={"observations":[{"status":"success","references":[{"ref_id":"PASSAGE::fixture:full","writer_citable":True,"authority_state":"source_bound_passage"}]}]}
    assert source_check_progress([scope()],notebook)[0]["read_status"]=="observed_not_semantically_verified"
    assert source_check_errors([scope()],notebook,SimpleNamespace(task_note=None))
    note=AuthorTaskNote(summary="Scope inspected",coverage=[{"criterion":scope()["criterion"],"status":"completed",
        "explanation":"Findings are stated with original qualifiers; causal uncertainty remains.","fields":["counterevidence","open_gaps"]}])
    assert not source_check_errors([scope()],notebook,SimpleNamespace(task_note=note))


def test_native_graph_checkpoints_and_delivers_mandatory_scope_before_first_decision():
    requests=[];ports=_ToolPorts()
    def turn(request):requests.append(request);return _handoff(request)
    graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=turn,
        evidence_tool=ports.evidence,finance_tool=ports.finance)).compile()
    seed=_input();seed['required_source_checks']=[scope()]
    result=graph.invoke(seed,{'recursion_limit':20})
    actual=requests[0]['task_context']['required_source_checks'][0]
    assert actual['missing_source_ids']==scope()['required_source_ids']
    assert 'mandatory inspection scope' in requests[0]['task_context']['source_check_guidance']
    assert result['required_source_checks'][0]['criterion']==scope()['criterion']


def test_native_submission_rejects_otherwise_valid_paper_with_unread_required_source():
    ports=_ToolPorts()
    model=_ScriptedModel([_evidence_action(),_finance_action(),_submission(),_handoff])
    graph=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=model,
        evidence_tool=ports.evidence,finance_tool=ports.finance)).compile()
    seed=_input();seed['required_source_checks']=[scope()]
    result=graph.invoke(seed,{'recursion_limit':40})
    assert result['final_submission'] is None
    issues=result['last_submission_attempt']['validation_issues']
    assert any('required_source_read_missing' in row['message'] for row in issues)
    assert model.requests[-1]['submission_to_repair']['candidate']['thesis']==_submission()({})['thesis']


def test_required_criteria_are_visible_in_public_task_outcome():
    from sec_agent.agent_runtime.task_outcome import task_outcome
    result=task_outcome({'phase':'ready_for_model_decision','required_source_checks':[scope()]})
    assert result['success_criteria']==[scope()['criterion']]
