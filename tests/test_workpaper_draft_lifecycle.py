"""Draft saving is persistent progress, not submission or financial acceptance."""
from copy import deepcopy
import json

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from sec_agent.agent_runtime.specialist_graph import (
    SaveWorkpaperEditsAction, FinalizeWorkpaperRevisionAction, WorkpaperEditError,
    SpecialistAgenticDependencies, build_specialist_agentic_state_graph,
    canonical_sha256,
)
from sec_agent.agent_runtime.workpaper_drafts import save_draft, finalize_draft
from sec_agent.agent_runtime.research_context_view import compact_current_context, public_operation
from sec_agent.agent_runtime.deepseek_structured_agents import (
    specialist_tools_for_actions, _NATIVE_SPECIALIST_TOOLS, _NATIVE_SPECIALIST_SYSTEM_PROMPT,
)
from test_workpaper_partial_edits import paper
from test_specialist_graph import _input, _ToolPorts, _evidence_action, _finance_action
from test_specialist_tool_batch import _batch, _handoff


def state():
    return {'agent_id': 'author', 'task': {'task_id': 'task'},
            'last_submission_attempt': {'arguments': paper(), 'accepted': False}}


def save_action(s, edits, operation='batch-1', **kw):
    base = (s.get('workpaper_draft') or {}).get('digest') or canonical_sha256(s['last_submission_attempt']['arguments'])
    return SaveWorkpaperEditsAction.model_validate_json(json.dumps({
        'action': 'save_workpaper_edits', 'context_digest': 'b'*64,
        'reason_summary': 'Offline draft lifecycle fixture.', 'operation_id': operation,
        'base_submission_digest': base, 'edits': edits, **kw}))


def setter(value='Changed draft.'):
    return {'op': 'set_field', 'path': '/thesis', 'value': value}


def test_edit_explanation_is_preserved_as_receipt_metadata_not_manuscript_content():
    s = state()
    original = deepcopy(s)
    edits = [{**setter(), 'value_note': 'Explain the changed field without adding prose.'},
             {'op': 'set_field', 'path': '/mechanism', 'value': 'Unrelated field updated.'}]
    action = save_action(s, edits)
    assert action.model_dump(mode='json')['edits'] == edits
    draft, receipt = save_draft(s, action)
    assert receipt['edit_notes'] == [{'edit_index': 0, 'path': '/thesis', 'value_note': edits[0]['value_note']}]
    assert draft['arguments']['thesis'] == 'Changed draft.'
    assert 'Explain the changed' not in json.dumps(draft['arguments'])
    assert s == original and not receipt['submitted'] and not receipt['accepted']
    restored = {**s, 'workpaper_draft': json.loads(json.dumps(draft))}
    repeated, again = save_draft(restored, action)
    assert repeated == draft and again['replayed'] and again['edit_notes'] == receipt['edit_notes']
    with pytest.raises(ValueError, match='operation_id_conflict'):
        save_draft(restored, save_action(s, [{**setter(), 'value_note': 'Different note.'}, edits[1]]))


def test_legacy_edit_and_operation_identity_do_not_gain_a_default_note():
    action = save_action(state(), [setter()])
    assert action.model_dump(mode='json')['edits'] == [setter()]
    _, receipt = save_draft(state(), action)
    assert 'edit_notes' not in receipt
    with pytest.raises(ValueError):
        save_action(state(), [{**setter(), 'unknown_metadata': 'Do not silently discard.'}])


def test_saved_draft_survives_serialization_replay_and_bad_batch():
    s = state(); old = deepcopy(s); a = save_action(s, [setter()])
    draft, receipt = save_draft(s, a)
    assert s == old and receipt['saved'] and not receipt['accepted'] and not receipt['submitted']
    assert receipt['replayed'] is False
    assert receipt['previous_draft_digest'] == a.base_submission_digest
    assert receipt['draft_digest'] != receipt['previous_draft_digest']
    from sec_agent.agent_runtime.deepseek_structured_agents import _agentic_semantic_value
    wire_receipt = _agentic_semantic_value(receipt)
    assert wire_receipt['previous_draft_digest'] == a.base_submission_digest
    assert wire_receipt['replayed'] is False
    s['workpaper_draft'] = json.loads(json.dumps(draft))
    replay, r = save_draft(s, a)
    assert replay == draft and r['replayed'] and replay['saved_batches'] == 1
    with pytest.raises(ValueError, match='operation_id_conflict'):
        save_draft(s, save_action(s, [setter('Different')]))
    with pytest.raises(WorkpaperEditError):
        save_draft(s, save_action(s, [setter('Would overwrite'), {'op':'set_field','path':'/missing','value':1}], 'bad'))
    assert s['workpaper_draft'] == draft and s['last_submission_attempt'] == old['last_submission_attempt']


def test_unchanged_value_with_new_operation_is_not_an_idempotent_replay():
    s = state()
    s['workpaper_draft'], _ = save_draft(s, save_action(s, [setter()]))
    next_draft, receipt = save_draft(s, save_action(s, [setter()], 'new-operation'))
    assert receipt['previous_draft_digest'] == receipt['draft_digest']
    assert receipt['saved'] and receipt['replayed'] is False
    assert next_draft['saved_batches'] == 2
    with pytest.raises(WorkpaperEditError):
        save_draft(s, save_action(s, [setter()], 'stale', base_submission_digest='0'*64))


def test_draft_owner_and_finalize_version_cannot_change():
    s=state();s['workpaper_draft'],_=save_draft(s,save_action(s,[setter()]))
    action=FinalizeWorkpaperRevisionAction(action='finalize_workpaper_revision',context_digest='b'*64,
        reason_summary='Offline',draft_digest='0'*64)
    with pytest.raises(ValueError,match='stale_finalize'): finalize_draft(s,action)
    s['agent_id']='other'
    with pytest.raises(ValueError,match='owner_mismatch'): finalize_draft(s,action)


def test_cross_field_incomplete_draft_can_be_saved_but_not_finalized():
    s=state();claim=s['last_submission_attempt']['arguments']['claims'][0]['claim_id']
    s['workpaper_draft'], receipt=save_draft(s,save_action(s,[{'op':'update_claim','claim_id':claim,
        'changes':{'kind':'reported_fact','evidence_ids':[]}}]))
    assert receipt['saved'] and receipt['draft_issues']
    action=FinalizeWorkpaperRevisionAction(action='finalize_workpaper_revision',context_digest='b'*64,
        reason_summary='Offline',draft_digest=s['workpaper_draft']['digest'])
    with pytest.raises(ValueError):finalize_draft(s,action)
    before=deepcopy(s)
    with pytest.raises(ValueError,match='field_invalid'):
        save_draft(s,save_action(s,[setter({'wrong':'type'})],'bad-type'))
    assert s==before


def test_current_view_is_compact_and_exact_draft_readback_works():
    s=state();s['workpaper_draft'],_=save_draft(s,save_action(s,[setter()]))
    d=s['workpaper_draft']
    c={'allowed_actions':['save_workpaper_edits','finalize_workpaper_revision'],'task_context':{},
       'submission_to_repair':{'candidate':d['arguments'],'draft_state':d}}
    view=compact_current_context(c)['submission_to_repair']
    assert 'candidate' not in view and view['latest_saved_fields']=={'/thesis':'Changed draft.'}
    read=view['candidate_readback']['arguments']['tool_call_id']
    record=public_operation([HumanMessage(content=json.dumps(c))],read)
    assert record is not None
    assert d['arguments']['narrative_markdown'] in json.dumps(record,ensure_ascii=False).replace('\\n','\n')


def test_wire_has_two_revision_actions_and_no_legacy_one_shot_guidance():
    tools=specialist_tools_for_actions(_NATIVE_SPECIALIST_TOOLS,['save_workpaper_edits','finalize_workpaper_revision'])
    assert set(tools)=={'SaveWorkpaperEditsAction','FinalizeWorkpaperRevisionAction'}
    assert 'applies the patch AND submits' not in _NATIVE_SPECIALIST_SYSTEM_PROMPT


def test_revision_guidance_defers_reconciliation_until_final_submission():
    from sec_agent.agent_runtime.revision_guidance import AUTHOR_REVISION_GUIDANCE
    from sec_agent.agent_runtime.specialist_graph import workpaper_revision_contract
    from langchain_core.utils.function_calling import convert_to_openai_tool
    schema = convert_to_openai_tool(SaveWorkpaperEditsAction)['function']
    assert 'even one field' in schema['description']
    assert 'Before final submission' in AUTHOR_REVISION_GUIDANCE
    assert 'update its affected prose and bindings together' not in AUTHOR_REVISION_GUIDANCE
    assert 'even one field or claim' in workpaper_revision_contract()['local_revision']
    assert 'that are needed for that step' in _NATIVE_SPECIALIST_SYSTEM_PROMPT


def test_single_ready_field_survives_before_later_related_prose():
    s = state()
    original = deepcopy(s['last_submission_attempt'])
    claim = original['arguments']['claims'][0]['claim_id']
    s['workpaper_draft'], r = save_draft(s, save_action(s, [
        {'op': 'update_claim', 'claim_id': claim, 'changes': {'statement': 'Updated fixture claim.'}}
    ]))
    assert r['saved'] and not r['accepted']
    assert s['workpaper_draft']['arguments']['narrative_markdown'] == original['arguments']['narrative_markdown']
    s = json.loads(json.dumps(s))
    s['workpaper_draft'], r = save_draft(s, save_action(s, [
        {'op': 'set_field', 'path': '/narrative_markdown', 'value': 'Related fixture prose updated later.'}
    ], 'related-prose'))
    assert s['workpaper_draft']['saved_batches'] == 2
    assert s['workpaper_draft']['arguments']['claims'][0]['statement'] == 'Updated fixture claim.'
    assert s['last_submission_attempt'] == original


def test_native_checkpoint_resume_save_error_finalize_error_then_local_fix():
    ports=_ToolPorts();requests=[]
    def model(r):
        requests.append(r);n=len(requests)
        if n==1:return _batch(r,[_evidence_action()({}),_finance_action()({})])
        if n==2:
            p=paper();p['claims'][0]['evidence_ids']=['E:unobserved'];return _batch(r,[p])
        c=r['submission_to_repair']['candidate'];digest=r['submission_to_repair']['base_submission_digest']
        if n == 6:
            assert r['submission_to_repair']['validation_feedback']['binding'] == 'current_candidate'
            assert r['submission_to_repair']['validation_feedback']['issues']
        if n in (3,4,6):
            edit=setter() if n==3 else {'op':'set_field','path':'/missing','value':1} if n==4 else {
                'op':'update_claim','claim_id':c['claims'][0]['claim_id'],'changes':{'evidence_ids':['E:DELL:Q1']}}
            return _batch(r,[{'action':'save_workpaper_edits','reason_summary':'Offline fixture',
                'operation_id':f'edit-{n}','base_submission_digest':digest,'edits':[edit]}])
        if n in (5,7):return _batch(r,[{'action':'finalize_workpaper_revision','reason_summary':'Offline fixture','draft_digest':digest}])
        return _handoff(r)
    deps=SpecialistAgenticDependencies(model_turn=model,evidence_tool=ports.evidence,finance_tool=ports.finance,
        allow_workpaper_field_edits=True)
    graph=build_specialist_agentic_state_graph(dependencies=deps).compile(checkpointer=InMemorySaver(),interrupt_after=['execute_native_tools'])
    cfg={'configurable':{'thread_id':'draft-test'},'recursion_limit':80}
    current=graph.invoke(_input(),cfg)
    while len(requests)<3:current=graph.invoke(None,cfg)
    assert current['workpaper_draft']['saved_batches']==1 and current.get('final_submission') is None
    saved=json.loads(json.dumps(current));baseline=deepcopy(saved['last_submission_attempt'])
    reentry = build_specialist_agentic_state_graph(dependencies=deps, recovery_state=saved).compile(
        interrupt_after=['initialize']).invoke(_input(), cfg)
    assert reentry['workpaper_draft'] == saved['workpaper_draft']
    assert reentry['max_model_turns'] == saved['max_model_turns']
    # Recreate graph/checkpointer and restore native state, as a persistent worker would.
    graph=build_specialist_agentic_state_graph(dependencies=deps).compile(checkpointer=InMemorySaver(),interrupt_after=['execute_native_tools'])
    graph.update_state(cfg,saved,as_node='execute_native_tools')
    current=graph.invoke(None,cfg) # bad second save
    assert current['workpaper_draft']==saved['workpaper_draft'] and current['last_submission_attempt']==baseline
    current=graph.invoke(None,cfg) # final validation rejects unobserved source
    assert current['phase']=='submission_rejected_with_typed_feedback' and not current['final_submission']
    assert current['workpaper_draft']==saved['workpaper_draft']
    reentry = build_specialist_agentic_state_graph(dependencies=deps, recovery_state=json.loads(json.dumps(current))).compile(
        interrupt_after=['initialize']).invoke(_input(), cfg)
    assert reentry['workpaper_draft'] == current['workpaper_draft']
    assert reentry['last_submission_attempt']['validation_issues'] == current['last_submission_attempt']['validation_issues']
    current=graph.invoke(None,cfg) # local fix saved, not accepted
    assert current['workpaper_draft']['saved_batches']==2 and not current['final_submission']
    current=graph.invoke(None,cfg) # final accepts
    assert current['phase']=='specialist_submission_accepted'
    assert current['final_submission']['thesis']=='Changed draft.'
    assert len(requests)==7


def test_budget_exhaustion_after_save_preserves_draft_without_completion():
    ports = _ToolPorts(); calls = []
    def model(r):
        calls.append(r)
        if len(calls) == 1: return _batch(r, [_evidence_action()({}), _finance_action()({})])
        if len(calls) == 2:
            p = paper(); p['claims'][0]['evidence_ids'] = ['E:unobserved']
            return _batch(r, [p])
        repair = r['submission_to_repair']
        return _batch(r, [{'action': 'save_workpaper_edits', 'operation_id': 'last-allowed-call',
            'reason_summary': 'Save before budget stop.', 'base_submission_digest': repair['base_submission_digest'],
            'edits': [setter()]}])
    deps = SpecialistAgenticDependencies(model_turn=model, evidence_tool=ports.evidence, finance_tool=ports.finance,
        allow_workpaper_field_edits=True, remaining_model_requests=lambda: 3 - len(calls))
    result = build_specialist_agentic_state_graph(dependencies=deps).compile().invoke(_input(), {'recursion_limit': 50})
    assert len(calls) == 3 and result['workpaper_draft']['saved_batches'] == 1
    assert result['workpaper_draft']['arguments']['thesis'] == 'Changed draft.'
    assert not result.get('final_submission')
    assert result['review_reason'] == 'shared_model_request_ceiling_reached_no_silent_completion'
