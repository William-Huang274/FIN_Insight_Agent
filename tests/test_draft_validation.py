"""Safe metadata repair does not drop content or accept completion claims."""
from copy import deepcopy
import json

import pytest

from sec_agent.agent_runtime.workpaper_drafts import save_draft
from sec_agent.agent_runtime.draft_validation import draft_change_status
from test_workpaper_draft_lifecycle import state as original_state, save_action, setter


def state():
    s=original_state()
    s['last_submission_attempt']['arguments']['task_note']['finding_responses']=[]
    return s


def response(**extra):
    return {'finding_id': 'F1', 'disposition': 'corrected',
            'explanation': '相关正文（第 2、3、7、8 节）、反向证据与未决项均已同步改写。', **extra}


def edit(row):
    return {'op': 'set_field', 'path': '/task_note/finding_responses', 'value': [row]}


@pytest.mark.parametrize('empty', [[], {}, None, ''])
def test_empty_unknown_response_metadata_corrected_and_journal_identity_preserved(empty):
    s=state(); original=deepcopy(s)
    a=save_action(s,[setter(),edit(response(unused_metadata=empty))]); raw=a.model_dump(mode='json')
    draft, receipt=save_draft(s,a)
    assert s==original and a.model_dump(mode='json')==raw
    assert receipt['saved'] and not receipt['submitted'] and not receipt['accepted']
    assert receipt['automatic_repairs']==[{'location':['task_note','finding_responses',0,'unused_metadata'],
        'operation':'remove_empty_unknown_response_field','original_value':empty}]
    assert draft['arguments']['task_note']['finding_responses']==[response()]
    s['workpaper_draft']=json.loads(json.dumps(draft))
    again, r=save_draft(s,a)
    assert again==draft and r['replayed'] and again['saved_batches']==1
    with pytest.raises(ValueError,match='operation_id_conflict'):
        save_draft(s,save_action(s,[setter(),edit(response())]))


@pytest.mark.parametrize('nonempty', [{'target':'C1'}, 'C1', False, 0, [123]])
def test_nonempty_or_scalar_unknown_metadata_is_not_discarded(nonempty):
    s=state(); before=deepcopy(s)
    with pytest.raises(ValueError,match='field_invalid'):
        save_draft(s,save_action(s,[setter(),edit(response(claim_ids=nonempty))]))
    assert s==before


@pytest.mark.parametrize('empty', [{}, None, ''])
def test_legacy_empty_claim_metadata_is_normalized_with_audit(empty):
    s=state()
    draft,r=save_draft(s,save_action(s,[edit(response(claim_ids=empty))]))
    assert draft['arguments']['task_note']['finding_responses']==[response(claim_ids=[])]
    assert r['automatic_repairs']==[{'location':['task_note','finding_responses',0,'claim_ids'],
        'operation':'normalize_empty_response_claim_ids','original_value':empty,'normalized_value':[]}]


def test_claim_associations_survive_save_restore_finalize_and_public_handoff():
    from sec_agent.agent_runtime.task_outcome import AuthorFindingResponse, task_outcome, public_task_outcome
    from sec_agent.agent_runtime.workpaper_drafts import finalize_draft
    from sec_agent.agent_runtime.specialist_graph import FinalizeWorkpaperRevisionAction
    s=state(); cid=s['last_submission_attempt']['arguments']['claims'][0]['claim_id']
    ids=[cid,'unresolved-navigation-id',cid]
    a=save_action(s,[edit(response(claim_ids=ids))]); before=deepcopy(s)
    draft,r=save_draft(s,a)
    assert s==before and not r['automatic_repairs']
    assert draft['arguments']['task_note']['finding_responses']==[response(claim_ids=ids)]
    assert r['change_status']['advisories'][0]['code']=='unknown_response_claim_ids'
    assert not r['change_status']['advisories'][0]['blocking']
    s['workpaper_draft']=json.loads(json.dumps(draft))
    again,replayed=save_draft(s,a)
    assert again==draft and replayed['replayed']
    final=finalize_draft(s,FinalizeWorkpaperRevisionAction(action='finalize_workpaper_revision',
        context_digest='b'*64,reason_summary='Offline contract check.',draft_digest=draft['digest']))
    assert final.task_note.finding_responses[0].claim_ids==ids
    s.update(phase='specialist_submission_accepted',final_submission=final.model_dump(mode='json'))
    public=public_task_outcome(task_outcome(s))
    assert public['author_note']['finding_responses'][0]['claim_ids']==ids
    assert 'unknown_claim_id:unresolved-navigation-id' in public['navigation_issues']
    assert AuthorFindingResponse.model_validate(response()).model_dump(mode='json')==response()


def test_known_fields_and_unrelated_fields_are_not_normalized():
    s=state(); before=deepcopy(s)
    with pytest.raises(ValueError,match='field_invalid'):
        save_draft(s,save_action(s,[edit(response(explanation=[],claim_ids=[]))]))
    assert s==before
    missing=response(claim_ids=['C1']);del missing['explanation']
    with pytest.raises(ValueError,match='field_invalid'):
        save_draft(s,save_action(s,[edit(missing)]))
    assert s==before
    note=deepcopy(s['last_submission_attempt']['arguments']['task_note']);note['unknown_empty']=[]
    with pytest.raises(ValueError,match='field_invalid'):
        save_draft(s,save_action(s,[{'op':'set_field','path':'/task_note','value':note}]))
    assert s==before


def test_actual_diff_not_completion_claim_controls_progress_across_save_and_restore():
    s=state(); original=deepcopy(s['last_submission_attempt']['arguments'])
    s['workpaper_draft'], r=save_draft(s,save_action(s,[setter(),edit(response(claim_ids=[]))]))
    status=r['change_status']
    assert not status['narrative_changed'] and not status['author_dispositions_verified']
    assert status['advisories'][0]['code']=='claimed_prose_update_but_narrative_unchanged'
    assert not status['advisories'][0]['blocking']
    assert s['workpaper_draft']['arguments']['task_note']['finding_responses'][0]['explanation']==response()['explanation']
    s=json.loads(json.dumps(s))
    s['workpaper_draft'], r=save_draft(s,save_action(s,[{'op':'set_field','path':'/narrative_markdown',
        'value':original['narrative_markdown']+'\nA related change.'}],'prose'))
    assert r['change_status']['narrative_changed'] and not r['change_status']['advisories']
    assert not r['change_status']['author_dispositions_verified'] # A text diff is not semantic approval.
    s['workpaper_draft'], r=save_draft(s,save_action(s,[{'op':'set_field','path':'/narrative_markdown',
        'value':original['narrative_markdown']}],'revert'))
    assert not r['change_status']['narrative_changed'] and r['change_status']['advisories']


@pytest.mark.parametrize('explanation', ['只改当前论断，正文尚未改写，不声称关联修订已经完成。',
                                       '正文尚未改写，但摘要已经更新；还需要检查相关内容。'])
def test_no_prose_edit_requirement_when_author_does_not_claim_one(explanation):
    s=state(); a=save_action(s,[edit(response(explanation=explanation))])
    draft,r=save_draft(s,a)
    assert r['saved'] and not r['change_status']['advisories']
    assert not draft.get('submitted')


def test_response_schema_comes_from_the_actual_contract():
    from sec_agent.agent_runtime.specialist_graph import workpaper_revision_contract
    from sec_agent.agent_runtime.task_outcome import AuthorFindingResponse
    assert json.loads(workpaper_revision_contract()['review_response_item_schema'])==AuthorFindingResponse.model_json_schema()


def test_native_save_normalizes_metadata_and_persists_before_budget_handoff():
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
    from test_specialist_graph import _input, _ToolPorts, _evidence_action, _finance_action
    from test_specialist_tool_batch import _batch
    from test_workpaper_partial_edits import paper
    ports=_ToolPorts(); calls=[]
    def model(r):
        calls.append(r)
        if len(calls)==1:return _batch(r,[_evidence_action()({}),_finance_action()({})])
        if len(calls)==2:
            p=paper();p['claims'][0]['evidence_ids']=['E:unobserved'];return _batch(r,[p])
        repair=r['submission_to_repair']
        note=deepcopy(repair['candidate']['task_note'])
        note['finding_responses']=[response(claim_ids=[repair['candidate']['claims'][0]['claim_id']],unused_metadata=[])]
        return _batch(r,[{'action':'save_workpaper_edits','reason_summary':'Save real-shaped metadata through native execution.',
            'operation_id':'normalized-save','base_submission_digest':repair['base_submission_digest'],
            'edits':[setter(),{'op':'set_field','path':'/task_note','value':note}]}])
    result=build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=model,evidence_tool=ports.evidence,finance_tool=ports.finance,
        allow_workpaper_field_edits=True,remaining_model_requests=lambda:3-len(calls))).compile().invoke(_input(),{'recursion_limit':50})
    assert len(calls)==3 and result['workpaper_draft']['saved_batches']==1
    assert not result.get('final_submission')
    assert result['review_reason']=='shared_model_request_ceiling_reached_no_silent_completion'
    receipt=result['last_edit_feedback']
    assert receipt['automatic_repairs'] and receipt['change_status']['advisories']
    assert result['workpaper_draft']['arguments']['task_note']['finding_responses'][0]['claim_ids']==[paper()['claims'][0]['claim_id']]
    assert result['notebook']['model_turn_records'][-1]['action']['tool_calls'][0]['args']['edits'][1]['value']['finding_responses'][0]['unused_metadata']==[]
