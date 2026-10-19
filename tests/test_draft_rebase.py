"""Stale metadata is recoverable only where the actual write set is safe."""
from copy import deepcopy
import json

import pytest

from sec_agent.agent_runtime.draft_rebase import assess_draft_rebase, import_ancestor_fingerprints, save_rebase_subset
from sec_agent.agent_runtime.workpaper_drafts import save_draft
from sec_agent.agent_runtime.specialist_graph import WorkpaperEditError
from test_workpaper_draft_lifecycle import state, save_action, setter


def test_disjoint_stale_save_rebases_and_keeps_original_idempotent_identity():
    s=state()
    stale=save_action(s,[{'op':'set_field','path':'/mechanism','value':'Revised mechanism.'}],'second')
    s['workpaper_draft'],_=save_draft(s,save_action(s,[setter()],'first'))
    before=deepcopy(s)
    draft,receipt=save_draft(s,stale)
    assert s==before and receipt['version_reconciliation']['safe_edit_indexes']==[0]
    assert draft['arguments']['thesis']=='Changed draft.'
    assert draft['arguments']['mechanism']=='Revised mechanism.'
    assert not receipt['submitted'] and not receipt['accepted']
    s['workpaper_draft']=json.loads(json.dumps(draft))
    again,r=save_draft(s,stale)
    assert again==draft and r['replayed'] and draft['saved_batches']==2


def test_overlap_keeps_whole_proposal_and_reports_only_conflicting_targets():
    s=state();cid=s['last_submission_attempt']['arguments']['claims'][0]['claim_id']
    a=save_action(s,[{'op':'set_field','path':'/mechanism','value':'New mechanism'},
        {'op':'update_claim','claim_id':cid,'changes':{'statement':'Author new assertion.'}}],'late')
    s['workpaper_draft'],_=save_draft(s,save_action(s,[{'op':'update_claim','claim_id':cid,
        'changes':{'statement':'An intervening saved assertion.'}}]))
    before=deepcopy(s);proposal=a.model_dump(mode='json')
    with pytest.raises(WorkpaperEditError) as error:save_draft(s,a)
    assert error.value.issues[0]['safe_edit_indexes']==[0]
    assert error.value.issues[0]['paths']==['/claims/0/statement']
    assert s==before and a.model_dump(mode='json')==proposal


def test_exact_fragment_guard_preserves_other_changes_but_ambiguity_never_rebases():
    s=state();base=s['last_submission_attempt']['arguments']['narrative_markdown']
    stale=save_action(s,[{'op':'str_replace','path':'/narrative_markdown',
        'old_string':'Expense table absent.','new_string':'Expense table available.'}],'late')
    s['workpaper_draft'],_=save_draft(s,save_action(s,[{'op':'set_field','path':'/narrative_markdown',
        'value':base+'\nAdditional preserved paragraph.'}]))
    draft,_=save_draft(s,stale)
    assert draft['arguments']['narrative_markdown']==(base+'\nAdditional preserved paragraph.').replace('Expense table absent.','Expense table available.')
    s['workpaper_draft'],_=save_draft(s,save_action(s,[{'op':'set_field','path':'/narrative_markdown',
        'value':base+'\nExpense table absent.'}],'duplicate'))
    with pytest.raises(WorkpaperEditError):save_draft(s,stale)


def test_legacy_ancestor_import_requires_same_owner_and_known_saved_digest():
    s=state();s['workpaper_draft'],_=save_draft(s,save_action(s,[setter()]))
    ancestor=deepcopy(s)
    stale=save_action(s,[{'op':'set_field','path':'/mechanism','value':'Another mechanism.'}],'late')
    s['workpaper_draft'],_=save_draft(s,save_action(s,[setter('Second thesis.')],'second'))
    del s['workpaper_draft']['version_fingerprints']
    with pytest.raises(WorkpaperEditError):save_draft(s,stale)
    imported=import_ancestor_fingerprints(s,ancestor)
    assert save_draft(imported,stale)[1]['saved']
    assert 'version_fingerprints' not in s['workpaper_draft']
    alien=deepcopy(ancestor);alien['agent_id']='other';alien['workpaper_draft']['owner']['agent_id']='other'
    with pytest.raises(ValueError):import_ancestor_fingerprints(s,alien)
    with pytest.raises(ValueError):import_ancestor_fingerprints(s,state())


def test_explicit_safe_subset_keeps_conflict_and_author_can_correct_only_remainder():
    from sec_agent.agent_runtime.specialist_graph import save_workpaper_revision, SaveWorkpaperEditsAction
    s=state()
    a=save_action(s,[{'op':'set_field','path':'/mechanism','value':'New mechanism.'},setter('Proposed thesis.')],'late')
    s['workpaper_draft'],_=save_draft(s,save_action(s,[setter('Intervening thesis.')]))
    before=deepcopy(s)
    with pytest.raises(ValueError):save_rebase_subset(s,a,[0,1])
    assert s==before
    draft,r,pending=save_rebase_subset(s,a,[0])
    assert r['recovery_selection']['deferred_original_indexes']==[1]
    assert draft['arguments']['thesis']=='Intervening thesis.' and pending.edits==(a.edits[1],)
    s['workpaper_draft']=json.loads(json.dumps(draft))
    again,replayed,_=save_rebase_subset(s,a,[0])
    assert again==draft and replayed['replayed'] and again['saved_batches']==2
    s['pending_workpaper_revision']=save_workpaper_revision(pending)
    correction=SaveWorkpaperEditsAction.model_validate_json(json.dumps({
        'action':'save_workpaper_edits','context_digest':'b'*64,'reason_summary':'Author explicitly reconciles overlap.',
        'operation_id':'resolved','base_submission_digest':draft['digest'],
        'pending_revision_digest':s['pending_workpaper_revision']['digest'],
        'edit_corrections':[{'edit_index':0,'edit':setter('Reconciled thesis.')}]}))
    fixed,receipt=save_draft(s,correction)
    assert fixed['arguments']['thesis']=='Reconciled thesis.' and fixed['arguments']['mechanism']=='New mechanism.'
    assert receipt['saved'] and not receipt['submitted']
