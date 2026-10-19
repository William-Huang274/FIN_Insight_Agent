from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from sec_agent.agent_runtime.workpaper_drafts import current_draft_issues, save_draft, finalize_draft
from sec_agent.agent_runtime.specialist_graph import FinalizeWorkpaperRevisionAction
from sec_agent.agent_runtime.calculation_bindings import calculation_binding_issues
from test_workpaper_draft_lifecycle import state,save_action


def draft_state():
    s=state();claim=s['last_submission_attempt']['arguments']['claims'][0]
    claim.update(kind='reported_fact',numeric_authority='not_applicable',fact_ids=[],
                 authority_note='Source disclosure and arithmetic are distinct.')
    action=save_action(s,[{'op':'update_claim','claim_id':claim['claim_id'],'changes':{
        'numeric_authority':'non_authoritative','fact_ids':['CALC::fixture'],
        'authority_note':'Computed cross-check CALC::fixture retained.'}}])
    draft,receipt=save_draft(s,action)
    return {**s,'workpaper_draft':draft},receipt


def test_save_and_resumed_feedback_locate_claim_and_offer_choices_without_editing():
    s,receipt=draft_state();before=deepcopy(s)
    issue=receipt['draft_issues'][0]
    assert receipt['saved'] and not receipt['submitted']
    assert issue['retained_calculation_ids']==['CALC::fixture']
    assert issue['current_fields']['kind']=='reported_fact'
    assert {r['kind'] for r in issue['classification_options']}=={'inference','calculation'}
    assert issue['edit']['op']=='update_claim'
    assert current_draft_issues(s['workpaper_draft']['arguments'])==receipt['draft_issues']
    assert s==before
    with pytest.raises(ValidationError):
        finalize_draft(s,FinalizeWorkpaperRevisionAction(action='finalize_workpaper_revision',
            context_digest='b'*64,reason_summary='Fixture',draft_digest=s['workpaper_draft']['digest']))


@pytest.mark.parametrize('kind,authority',[('inference','not_applicable'),('calculation','non_authoritative')])
def test_author_selected_pair_only_changes_fields_and_retains_calc(kind,authority):
    s,_=draft_state();c=s['workpaper_draft']['arguments']['claims'][0]
    action=save_action(s,[{'op':'update_claim','claim_id':c['claim_id'],
        'changes':{'kind':kind,'numeric_authority':authority}}],'correct-pair')
    draft,receipt=save_draft(s,action)
    assert not receipt['draft_issues']
    assert draft['arguments']['claims'][0]['fact_ids']==c['fact_ids']==['CALC::fixture']
    assert draft['arguments']['claims'][0]['statement']==c['statement']


def test_removing_calc_to_avoid_classification_does_not_hide_dependent_text():
    s,_=draft_state();c=s['workpaper_draft']['arguments']['claims'][0]
    prior=deepcopy(s['workpaper_draft']['arguments'])
    candidate=deepcopy(prior);candidate['claims'][0]['fact_ids']=[]
    issues=calculation_binding_issues(candidate,{'observations':[]},prior)
    assert any(i['code']=='calculation_binding_missing' and i['source_id']=='CALC::fixture' for i in issues)
