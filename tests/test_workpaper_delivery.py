import json
from copy import deepcopy
import pytest
from sec_agent.agent_runtime.workpaper_delivery import decode_workpaper_arguments
from sec_agent.agent_runtime.dell_specialist_agentic_graph import SubmitWorkpaperAction
from sec_agent.agent_runtime.workpaper_intervention import recover_workpaper
from sec_agent.agent_runtime.dell_reference_vertical_contracts import canonical_sha256
from test_research_session import _new_worker_fixture


@pytest.mark.parametrize('suffix,accepted', [('}', True), ('}}', False), ('{}', False), ('garbage', False)])
def test_only_single_extra_brace_is_eligible(suffix, accepted):
    original = {'narrative_markdown': 'Preserve "quotes" and {braces}.', 'claims': []}
    parsed, valid, repair = decode_workpaper_arguments(json.dumps(original)+suffix)
    assert parsed == original and valid == accepted
    assert bool(repair) == accepted


def test_truncated_claim_does_not_lose_already_written_body_or_execute():
    parsed, valid, _ = decode_workpaper_arguments('{"narrative_markdown":"Saved work", "claims":[{"statement":"broken')
    assert parsed == {'narrative_markdown':'Saved work'} and not valid
    assert not decode_workpaper_arguments('{"a":1,"a":2}}')[1]


@pytest.mark.parametrize('partial',[False,True])
def test_native_submission_recovery_or_readable_handoff(partial):
    from sec_agent.agent_runtime.dell_specialist_agentic_graph import DellSpecialistAgenticDependencies, build_dell_specialist_agentic_state_graph
    from test_dell_specialist_tool_batch import _batch
    from test_dell_specialist_agentic_graph import _input, _evidence_action, _finance_action, _submission, _ToolPorts
    calls,ports=[],_ToolPorts()
    def model(request):
        calls.append(request)
        if len(calls)==1:
            return _batch(request,[_evidence_action()({}),_finance_action()({})])
        candidate=_submission()(request)
        raw=json.dumps(candidate)+'}'
        if partial:
            raw=json.dumps({'action':'submit_workpaper','narrative_markdown':candidate['narrative_markdown']})[:-1]+',"claims":['
        return {'action':'native_tool_batch','context_digest':request['context_digest'],'tool_calls':[
            {'id':'saved-call','name':'SubmitWorkpaperAction','args':raw,'type':'invalid_tool_call'}]}
    result=build_dell_specialist_agentic_state_graph(dependencies=DellSpecialistAgenticDependencies(
        model_turn=model,evidence_tool=ports.evidence,finance_tool=ports.finance)).compile().invoke(
            {**_input(),'max_model_turns':2},config={'recursion_limit':32})
    if partial:
        assert result['final_submission'] is None
        assert result['last_submission_attempt']['readable_candidate']['narrative_markdown']==_submission()({})['narrative_markdown']
    else:
        assert result['final_submission']
        assert result['last_submission_attempt']['format_recovery']=='redundant_closing_brace'
    assert len(ports.calls)==2


def test_shared_quote_mapping_preserves_explicit_claim_references_only():
    paper = _new_worker_fixture()['final_submission']
    ref = paper['claims'][0]['evidence_ids'][0]
    paper['citation_quotes'] = {ref: 'shared source quote'}
    before = deepcopy(paper)
    result = SubmitWorkpaperAction.model_validate_json(json.dumps(paper))
    assert result.claims[0].citation_quotes[ref] == 'shared source quote'
    assert result.claims[1].citation_quotes == {}
    assert paper == before
    with pytest.raises(ValueError, match='not_referenced'):
        SubmitWorkpaperAction.model_validate_json(json.dumps({**paper,'citation_quotes':{'unknown':'quote'}}))


def test_human_workpaper_recovery_keeps_old_failure_and_source_gates():
    paper = _new_worker_fixture()
    original = deepcopy(paper['final_submission'])
    paper.update(final_submission=None, phase='specialist_human_review_handoff_emitted',
                 last_submission_attempt={'arguments':original,'accepted':False})
    state = {'case_papers':[], 'research_failed_workpapers':[{'task_id':paper['task']['task_id'],'agent_state':paper}],
             'research_tasks':[{'task_id':paper['task']['task_id'],'owner_role':'financials-analyst'}]}
    candidate = {**original,'narrative_markdown':original['narrative_markdown']+'\nHuman clarified the boundary.'}
    request = {'task_id':paper['task']['task_id'],'base_agent_digest':canonical_sha256(paper),
               'submission':candidate,'confirmed':True,'reason':'Correct scope'}
    before = deepcopy(state)
    result = recover_workpaper(state,request,owner='authorized-operator')
    assert state == before and result['continue_remaining_research']
    assert result['case_papers'][0]['final_submission']['narrative_markdown'] == candidate['narrative_markdown']
    edit = result['human_edits'][0]
    assert edit['number'] == 1 and edit['papers'][0]['actor'] == 'financials-analyst'
    assert original['narrative_markdown'] in edit['papers'][0]['before']
    invalid = deepcopy(request)
    invalid['submission']['claims'][0]['evidence_ids'] = ['E:UNOBSERVED']
    with pytest.raises(ValueError,match='invalid_references'):
        recover_workpaper(state,invalid,owner='authorized-operator')
    with pytest.raises(ValueError,match='stale'):
        recover_workpaper(state,{**request,'base_agent_digest':'f'*64},owner='operator')


def test_new_parent_checkpoint_does_not_resume_old_pending_child_dispatch():
    from typing import TypedDict
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import interrupt
    class State(TypedDict, total=False):
        papers: list
        allow_new: bool
        complete: bool
    called=[]
    child=StateGraph(State)
    child.add_node('lead',lambda s:{})
    def worker(s):
        called.append('old-worker')
        interrupt('pending obsolete scope')
        return {}
    child.add_node('worker',worker)
    child.add_edge(START,'lead')
    child.add_conditional_edges('lead',lambda s:'worker' if s['allow_new'] else END)
    child.add_edge('worker',END)
    parent=StateGraph(State)
    parent.add_node('attention',lambda s:{})
    parent.add_node('research',child.compile())
    parent.add_node('deliver',lambda s:{'complete':True})
    parent.add_edge(START,'attention');parent.add_edge('attention','research')
    parent.add_edge('research','deliver');parent.add_edge('deliver',END)
    graph=parent.compile(checkpointer=InMemorySaver())
    config={'configurable':{'thread_id':'native-fresh-parent'}}
    graph.invoke({'papers':['retained'],'allow_new':True},config)
    old=graph.get_state(config)
    fresh=graph.update_state(config,{'allow_new':False},as_node='attention')
    assert graph.get_state(fresh).tasks[0].id!=old.tasks[0].id
    result=graph.invoke(None,fresh)
    assert result['complete'] and result['papers']==['retained'] and called==['old-worker']
    assert graph.get_state(old.config).values['allow_new'] is True


def test_human_scope_confirmation_is_review_not_financial_acceptance():
    from sec_agent.agent_runtime.workpaper_intervention import review_saved_workpapers
    paper=_new_worker_fixture()
    state={'case_papers':[paper],'research_tasks':[{'task_id':paper['task']['task_id']}], 'question':'Original question'}
    decision={'confirmed':True,'reason':'The original requested scope is covered by this paper; independently review it.',
        'base_papers_digest':canonical_sha256(state['case_papers']),
        'execution_plan':{'depth':'integrated','rationale':'Independent source and final report review remain necessary.',
            'omitted_steps_reason':'No distinct synthesis responsibility exists for the saved workpapers.',
            'escalation_conditions':'Material unresolved facts must be disclosed for human attention.'}}
    out=review_saved_workpapers(state,decision,owner='operator')
    assert out['phase']=='research_reviewing' and 'report' not in out
    assert out['research_handoff']['origin']=='human_scope_confirmation'
    with pytest.raises(ValueError,match='all_original_workpapers'):
        review_saved_workpapers({**state,'research_tasks':[{'task_id':'missing'}]},decision,owner='operator')


def test_human_writer_handoff_preserves_incomplete_review_and_blocks_material_gaps():
    from sec_agent.agent_runtime.workpaper_intervention import write_after_incomplete_review
    from copy import deepcopy
    review = {'phase': 'case_review_incomplete', 'counter': {'status': 'incomplete_no_submission'},
              'verifier': {'status': 'review_submitted', 'review': {'findings': [], 'unresolved_data_requests': []}}}
    state = {'case_papers': [_new_worker_fixture()], 'case_review': review,
             'research_handoff': {}, 'research_stop_reason': 'independent_review_incomplete_no_report_acceptance'}
    decision = {'confirmed': True, 'reason': 'The operator checks saved financial evidence and requires final human confirmation.',
                'base_review_digest': canonical_sha256(review), 'base_papers_digest': canonical_sha256(state['case_papers'])}
    before = deepcopy(state)
    result = write_after_incomplete_review(state, decision, owner='operator')
    assert result['phase'] == 'research_writing' and 'report' not in result and 'case_review' not in result
    assert state == before and result['research_handoff']['human_review_direction']['final_human_confirmation_required']
    for change in ({'unresolved_data_requests': ['Missing source receipt']}, {'findings': [{'severity': 'material'}]}):
        broken = deepcopy(state)
        broken['case_review']['verifier']['review'].update(change)
        with pytest.raises(ValueError, match='resolution_of_material_or_data'):
            write_after_incomplete_review(broken, {**decision, 'base_review_digest': canonical_sha256(broken['case_review'])}, owner='operator')
    with pytest.raises(ValueError, match='unconfirmed_or_stale'):
        write_after_incomplete_review(state, {**decision, 'confirmed': False}, owner='operator')


def test_human_review_amendment_preserves_sources_and_requires_all_dispositions():
    from copy import deepcopy
    from sec_agent.agent_runtime.workpaper_intervention import amend_reviewed_workpapers
    from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts
    paper = _new_worker_fixture()
    review = {'phase':'case_review_incomplete','counter':{'review':{'findings':[{'finding_id':'F1','severity':'material','paper_id':'P01'}], 'unresolved_data_requests':['Optional alternative definition']}}}
    state = {'case_papers':[paper], 'case_review':review, 'research_handoff':{},
             'research_stop_reason':'independent_review_incomplete_no_report_acceptance'}
    old=deepcopy(state)
    decision={'confirmed':True,'reason':'Human has read the original source and corrected the affected working paper.',
        'base_papers_digest':canonical_sha256(state['case_papers']), 'base_review_digest':canonical_sha256(review),
        'base_edits_digest':canonical_sha256([]), 'papers':[{'paper_id':'P01','after':'Human corrected prose; original source facts remain independently readable.'}],
        'dispositions':{'counter:finding:F1':{'decision':'corrected','reason':'Corrected the specific misleading sentence in the responsible paper.'},
                        'counter:request:0':{'decision':'outside_requested_scope','reason':'The user requested the standard metric only; alternative definition remains disclosed.'}}}
    result=amend_reviewed_workpapers(state,decision,owner='operator')
    assert state==old and 'case_review' not in result and 'case_papers' not in result and 'report' not in result
    assert result['phase']=='research_writing' and result['human_edits'][0]['number']==1
    assert result['research_handoff']['human_review_direction']['final_human_confirmation_required']
    current=DellCaseArtifacts(state['case_papers']).with_human_edits(result['human_edits'])
    assert current.read_paper('P01')['narrative_markdown']==decision['papers'][0]['after']
    assert current.read_paper('P01')['claims']==DellCaseArtifacts(state['case_papers']).read_paper('P01')['claims']
    for patch in ({'confirmed':False},{'base_edits_digest':'0'*64},{'dispositions':{}},{'papers':[]}):
        with pytest.raises(ValueError):amend_reviewed_workpapers(state,{**decision,**patch},owner='operator')
