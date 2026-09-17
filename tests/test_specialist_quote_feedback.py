"""Precise repair navigation does not change source or acceptance authority."""
from copy import deepcopy
from types import SimpleNamespace
import jsonpatch
import json
import pytest
from sec_agent.agent_runtime.specialist_graph import _quote_issue_location
from sec_agent.research_foundation.source_quotes import contains_source_quote


@pytest.mark.parametrize("as_list", [True, False])
def test_rejected_quote_resolves_exact_field_and_original_line_without_repair(as_list):
    source_id = "PASSAGE::a/b~c:2:4::digest"
    source = "Operating income |  |  | 120 |  |  |  | 160 |"
    quote = "Operating income |  | 120 |  |  |  | 160"
    value = ["already correct", quote] if as_list else quote
    claim = SimpleNamespace(claim_id="C8", citation_quotes={source_id:value})
    paper = SimpleNamespace(claims=[claim])
    notebook = SimpleNamespace(observations=[SimpleNamespace(content=[{"passage_id":source_id,"passage":source}]),
        SimpleNamespace(content=[{"passage_id":"OTHER-PERIOD","passage":quote}])])
    document = {"claims":[{"citation_quotes":{source_id:deepcopy(value)}}]}
    error = f"source_quote_not_in_observed_passage:{source_id}:claim=C8:quote_index={1 if as_list else 0}:copy_exact_contiguous_source_text"
    result = _quote_issue_location(error, paper, notebook)
    pointer = jsonpatch.JsonPointer.from_parts(result["location"])
    assert result["path"] == pointer.path
    assert pointer.resolve(document) == quote
    assert result["source_line_candidates"] == [source]
    assert result["origin"] == "runtime_quote_navigation_not_confirmation"
    assert claim.citation_quotes[source_id] == value
    assert not contains_source_quote(source, quote)
    assert contains_source_quote(source, result["source_line_candidates"][0])
    assert "ReviseWorkpaperAction" in result["instruction"]


def test_quote_navigation_does_not_guess_missing_source_or_swallow_other_errors():
    claim = SimpleNamespace(claim_id="C1",citation_quotes={"P":"Some original text"})
    notebook = SimpleNamespace(observations=[])
    issue = _quote_issue_location("source_quote_not_in_observed_passage:P:claim=C1:quote_index=0:copy_exact",
        SimpleNamespace(claims=[claim]), notebook)
    assert issue["source_line_candidates"] == []
    assert _quote_issue_location("unknown_fact_id:P",SimpleNamespace(),notebook) is None


def test_current_candidate_feedback_reaches_next_model_request_and_old_binding_is_explicit():
    from sec_agent.agent_runtime.specialist_graph import SpecialistNotebook, _model_request
    from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
    from test_workpaper_partial_edits import paper
    from test_specialist_graph import _input, _ToolPorts
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
    from test_specialist_tool_batch import _handoff
    ports=_ToolPorts()
    state=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=_handoff,evidence_tool=ports.evidence,finance_tool=ports.finance)).compile().invoke(_input())
    candidate=paper(); issue={'location':['claims',0,'statement'],'message':'Check current quote'}
    state['last_submission_attempt']={'arguments':candidate,'accepted':False,'validation_issues':[issue],
        'validated_candidate_digest':canonical_sha256(candidate)}
    notebook=SpecialistNotebook.model_validate_json(__import__('json').dumps(state['notebook']))
    request=_model_request(state=state,notebook=notebook,allow_workpaper_field_edits=True)
    feedback=request['submission_to_repair']['validation_feedback']
    assert feedback['issues']==[issue] and feedback['binding']=='current_candidate'
    del state['last_submission_attempt']['validated_candidate_digest']
    old=_model_request(state=state,notebook=notebook,allow_workpaper_field_edits=True)
    assert old['submission_to_repair']['validation_feedback']['binding'].startswith('legacy_or_attempt')


@pytest.mark.parametrize('failure', ['', 'sign', 'value', 'ambiguous'])
def test_specialist_reuses_unique_layout_parser_without_changing_assertions(failure):
    from test_workpaper_partial_edits import paper
    from sec_agent.agent_runtime.specialist_graph import SubmitWorkpaperAction, _normalize_submission_quotes
    value=paper(); source_id='PASSAGE::financial-table'
    quote='Income | 10 | (20) |'
    source='Income |  | 10 |  | (20) |\n'
    if failure=='sign': quote=quote.replace('(20)','20')
    if failure=='value': quote=quote.replace('10','11')
    if failure=='ambiguous': source*=2
    value['claims'][0]['evidence_ids']=[source_id]
    value['claims'][0]['citation_quotes']={source_id:[quote]}
    original=SubmitWorkpaperAction.model_validate_json(json.dumps(value))
    before=original.model_dump(mode='json')
    notebook=SimpleNamespace(observations=[SimpleNamespace(content=[{'passage_id':source_id,'passage':source}])])
    normalized,records=_normalize_submission_quotes(original,notebook)
    assert original.model_dump(mode='json')==before
    assert normalized.narrative_markdown==original.narrative_markdown
    assert normalized.claims[0].statement==original.claims[0].statement
    if failure:
        assert records==[] and normalized==original
    else:
        assert normalized.claims[0].citation_quotes[source_id]==[source.rstrip()]
        assert records[0]['origin']=='runtime_compatibility_parse'
        assert records[0]['financial_semantics_verified'] is False
