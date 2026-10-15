"""Offline lifecycle replay on copies of an actual request/state/truncated response.

Complete edit objects are mechanical fixtures ONLY, never recovered financial
submissions. Original artifacts and request limits remain unchanged. No API calls.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from langchain_core.messages import HumanMessage
from sec_agent.agent_runtime.specialist_graph import (
    SaveWorkpaperEditsAction, FinalizeWorkpaperRevisionAction, WorkpaperEditError,
    SpecialistAgenticDependencies, build_specialist_agentic_state_graph,
    canonical_sha256, _model_request, SpecialistNotebook,
)
from sec_agent.agent_runtime.workpaper_drafts import save_draft, finalize_draft
from sec_agent.agent_runtime.research_context_view import compact_current_context, public_operation


def deny(*args, **kwargs):
    raise AssertionError('offline_network_or_data_call_forbidden')


def run(args):
    inputs = [args.wire, args.state, args.audit]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    wire = json.loads(args.wire.read_text(encoding='utf8'))
    envelope = next(json.loads(m['content']) for m in wire['messages']
                    if m['role'] == 'user' and 'current_context' in m['content'])
    context = envelope['current_context']
    candidate = context['submission_to_repair']['candidate']
    records = [json.loads(line) for line in args.audit.read_text(encoding='utf8').splitlines()]
    raw = next(r['raw_response'] for r in records if r.get('raw_response'))
    incomplete = raw['invalid_tool_calls'][0]['args']
    pos = incomplete.index('[', incomplete.index('"edits":')) + 1
    edits = []
    while pos < len(incomplete):
        while pos < len(incomplete) and incomplete[pos] in ' ,\n\r': pos += 1
        try:
            edit, pos = json.JSONDecoder().raw_decode(incomplete, pos)
        except json.JSONDecodeError:
            break
        edits.append(edit)
    assert edits, 'no complete fixture objects'
    state = json.loads(args.state.read_text(encoding='utf8'))
    original = deepcopy(state)
    assert state['last_submission_attempt']['arguments'] == candidate
    state['workpaper_draft'] = None
    original_attempt = deepcopy(state['last_submission_attempt'])
    sizes = []
    for index, edit in enumerate(edits):
        digest = (state.get('workpaper_draft') or {}).get('digest') or canonical_sha256(candidate)
        action = SaveWorkpaperEditsAction.model_validate_json(json.dumps({
            'action': 'save_workpaper_edits', 'context_digest': '0'*64,
            'reason_summary': 'OFFLINE MECHANICAL FIXTURE ONLY',
            'operation_id': f'offline-{index}', 'base_submission_digest': digest, 'edits': [edit]}))
        draft, receipt = save_draft(state, action)
        assert receipt['saved'] and not receipt['submitted'] and not receipt['accepted']
        state['workpaper_draft'] = draft
        # Persistence boundary after EVERY batch: fresh deserialized state.
        state = json.loads(json.dumps(state))
        same, replayed = save_draft(state, action)
        assert same == draft and replayed['replayed']
        assert state['last_submission_attempt'] == original_attempt
        assert not state.get('final_submission')
        sizes.append(len(json.dumps(action.model_dump(mode='json'), ensure_ascii=False)))
    before_bad = deepcopy(state)
    bad = action.model_copy(update={'operation_id': 'bad-fixture',
        'base_submission_digest': state['workpaper_draft']['digest']})
    bad = SaveWorkpaperEditsAction.model_validate_json(json.dumps({**bad.model_dump(mode='json'),
        'edits': [{'op': 'set_field', 'path': '/thesis', 'value': 'Must not persist'},
                  {'op': 'update_claim', 'claim_id': 'ABSENT_OFFLINE_ONLY', 'changes': {'statement': 'Invalid'}}]}))
    try:
        save_draft(state, bad)
        raise AssertionError('bad batch must fail')
    except WorkpaperEditError:
        pass
    assert state == before_bad
    request = _model_request(state=state, notebook=SpecialistNotebook.model_validate_json(json.dumps(state['notebook'])),
        allow_workpaper_field_edits=True)
    view = compact_current_context(request)
    repair = view['submission_to_repair']
    assert 'candidate' not in repair and repair['draft_state']['saved_batches'] == len(edits)
    readback = public_operation([HumanMessage(content=json.dumps(request))],
        repair['candidate_readback']['arguments']['tool_call_id'])
    assert readback is not None
    # Finalization assembles the saved draft, then runs the SAME full validator.
    final = FinalizeWorkpaperRevisionAction(action='finalize_workpaper_revision', context_digest='0'*64,
        reason_summary='OFFLINE FINAL VALIDATION ONLY', draft_digest=state['workpaper_draft']['digest'])
    proposal = finalize_draft(state, final)
    validator = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=deny, evidence_tool=deny, finance_tool=deny, allow_workpaper_field_edits=True,
        authoring_enabled=bool(state.get('authoring_context')),
        enforce_case_route_requirements=state.get('task_context', {}).get('instruction_source') != 'current_user_research_request'))
    validate_state = {**state, 'pending_action': proposal.model_dump(mode='json')}
    result = validator.nodes['validate_submission'].runnable.invoke(validate_state)
    assert not result.get('final_submission'), 'incomplete four-edit fixture must not pass final acceptance'
    assert result['phase'] == 'submission_rejected_with_typed_feedback'
    assert state['workpaper_draft'] == before_bad['workpaper_draft']
    assert state['notebook']['observations'] == original['notebook']['observations']
    assert {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs} == hashes
    report = {'network_disabled': True, 'paid_calls': 0, 'financial_artifacts_promoted': 0,
        'original_files_unchanged': True, 'original_candidate_unchanged': True,
        'saved_batches': len(edits), 'restart_after_each_save': True, 'idempotent_replay': True,
        'bad_batch_preserves_all_prior_edits': True, 'save_does_not_complete': True,
        'full_validation_rejects_incomplete_fixture': True, 'rejected_draft_retained': True,
        'full_validation_issues': result['last_submission_attempt']['validation_issues'],
        'actual_material_count': len(envelope.get('current_materials', [])),
        'source_observations_unchanged': True, 'draft_readback_resolves': True,
        'batch_action_characters': sizes,
        'finalize_action_characters': len(json.dumps(final.model_dump(mode='json'), ensure_ascii=False)),
        'execution_budget_unchanged': context['execution_budget'], 'input_hashes': hashes,
        'scope': 'Mechanical complete objects from truncated output used on private copies only. No claim of model behavior or reduced total cost.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'full_validation_issues','input_hashes','execution_budget_unchanged'}}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('wire','state','audit','output'): parser.add_argument('--'+key, type=Path, required=True)
    with patch.object(socket.socket, 'connect', deny), patch('socket.create_connection', deny):
        run(parser.parse_args())
