"""Replay real revision requests and staged-save lifecycle without network calls.

Inputs are external private records. Synthetic edits are copies for engineering
validation only; never promote them into an author's financial workpaper.
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
from langchain_core.messages import AIMessage, ToolMessage, messages_from_dict, messages_to_dict
from pydantic import SecretStr
from sec_agent.agent_runtime.deepseek_structured_agents import (
    ReasoningPreservingChatDeepSeek, _project_agentic_specialist_request,
)
from sec_agent.agent_runtime.research_context_view import (
    working_view, public_operation, history_operation_page, INITIAL_CONTEXT_ID,
)
from sec_agent.agent_runtime.specialist_graph import (
    SaveWorkpaperEditsAction, FinalizeWorkpaperRevisionAction, WorkpaperEditError,
    SpecialistNotebook, _model_request, SpecialistAgenticDependencies,
    build_specialist_agentic_state_graph, canonical_sha256,
)
from sec_agent.agent_runtime.workpaper_drafts import save_draft, finalize_draft


def deny(*args, **kwargs):
    raise AssertionError('offline_network_or_model_call_forbidden')


def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)


def identity(row):
    return row.get('passage_id') or row.get('numeric_fact_id') or row.get('calculation_id') or row.get('fact_id')


def message_objects(messages):
    for message in messages:
        if message['role'] not in {'user', 'tool'}:
            continue
        try:
            yield from objects(json.loads(message['content']))
        except (ValueError, TypeError):
            continue


def run(args):
    files = [args.audit, args.state, *sorted(args.wire_dir.glob('*.private.json'))]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    events = [json.loads(line) for line in args.audit.read_text(encoding='utf8').splitlines()]
    events = [e for e in events if e.get('raw_response')]
    wires = [json.loads(p.read_text(encoding='utf8')) for p in sorted(args.wire_dir.glob('*.private.json'))]
    assert len(events) == len(wires) == 3, 'Expected the three actual stopped validation requests'
    originals = next(json.loads(m['content'])['current_materials'] for m in wires[0]['messages']
                     if m['role'] == 'user' and 'current_materials' in json.loads(m['content']))
    assert len(originals) == 7
    chat = ReasoningPreservingChatDeepSeek(model=wires[0]['model'], api_key=SecretStr('offline'),
        tool_context_policy='task_boundary', research_checkpoint_tokens=48000, max_retries=0,
        use_responses_api=False)
    args.output.mkdir(parents=True, exist_ok=True)
    results = []

    def check(rows, label, old_wire, expected=originals):
        before = deepcopy(rows)
        # Actual SDK request projection, not just the source selection helper.
        payload = chat._get_request_payload(rows, tools=old_wire['tools'], tool_choice='auto')
        wire = {**old_wire, 'messages': payload['messages']}
        material = list(message_objects(wire['messages']))
        for original in expected:
            ref = identity(original)
            candidates = [r for r in material if identity(r) == ref]
            assert original in candidates, (label, ref, 'original/binding changed or absent')
        projected = working_view(rows)
        assert working_view(projected) == projected and rows == before
        view = next(json.loads(m.content) for m in projected if m.additional_kwargs.get('fin_research_working_view'))
        readbacks = []
        for original in originals:
            ref = identity(original)
            for route in view['operation_catalog']:
                saved = public_operation(rows, route['tool_call_id'])
                if saved is None:
                    continue
                selected = history_operation_page(saved, source_ids=[ref])
                if any(identity(r) == ref for r in objects(selected['receipt']['result'])):
                    readbacks.append({'source_id': ref, 'tool_call_id': route['tool_call_id']})
                    break
            else:
                raise AssertionError((label, ref, 'missing executable saved readback'))
        # Full original archive stays byte-equivalent through the projection.
        for cid in [INITIAL_CONTEXT_ID, *[c['id'] for m in rows if isinstance(m, AIMessage) for c in m.tool_calls]]:
            assert public_operation(rows, cid) == public_operation(before, cid)
        (args.output / (label + '.private.json')).write_text(json.dumps(wire, ensure_ascii=False), encoding='utf8')
        results.append({'stage': label, 'expected_materials_exact': len(expected), 'readbacks': readbacks,
            'sdk_characters': len(json.dumps(wire, ensure_ascii=False)), 'material_focus': view['material_focus']})
        return view

    for i, (event, wire) in enumerate(zip(events, wires), 1):
        rows = messages_from_dict([{'type': m['type'], 'data': m} for m in event['messages']])
        check(rows, f'actual-request-{i}', wire)
    # Do not apply the stopped third response or invent a provider response.
    # Exercise local saves on the actual third input, using isolated copies.
    state = json.loads(args.state.read_text(encoding='utf8'))
    old_attempt = deepcopy(state['last_submission_attempt'])
    old_observations = deepcopy(state['notebook']['observations'])

    def append(cid, name, arguments, receipt, status='success'):
        request = _model_request(state=state,
            notebook=SpecialistNotebook.model_validate_json(json.dumps(state['notebook'])),
            allow_workpaper_field_edits=True)
        # Match the native adapter's continuation envelope: observations already
        # live in canonical receipts, never paste the whole host state again.
        delta = _project_agentic_specialist_request(request)
        delta['progress'] = {**delta['progress'], 'prior_actions': [], 'observations': []}
        rows.extend([AIMessage(content='', tool_calls=[{'id': cid, 'name': name, 'args': arguments}]),
            ToolMessage(tool_call_id=cid, name=name, status=status,
                content=json.dumps({'result': receipt, 'current_context': delta}))])

    for i, field in enumerate(('thesis', 'narrative_markdown'), 1):
        candidate = (state.get('workpaper_draft') or {}).get('arguments') or old_attempt['arguments']
        action = SaveWorkpaperEditsAction.model_validate_json(json.dumps({
            'action': 'save_workpaper_edits', 'context_digest': '0'*64,
            'reason_summary': 'OFFLINE LIFECYCLE FIXTURE ONLY', 'operation_id': f'offline-{i}',
            'base_submission_digest': canonical_sha256(candidate), 'edits': [
                {'op': 'set_field', 'path': '/' + field, 'value': candidate[field] + '\n[OFFLINE FIXTURE]'}]}))
        state['workpaper_draft'], receipt = save_draft(state, action)
        assert receipt['saved'] and not receipt['accepted'] and not receipt['submitted']
        append(f'offline-save-{i}', 'SaveWorkpaperEditsAction', action.model_dump(mode='json'), receipt)
        state = json.loads(json.dumps(state))
        rows = messages_from_dict(json.loads(json.dumps(messages_to_dict(rows))))
        v = check(rows, f'saved-{i}-resumed', wires[-1])
        draft_route = v['current_context']['submission_to_repair']['candidate_readback']['arguments']['tool_call_id']
        assert public_operation(rows, draft_route) is not None
    saved_state = deepcopy(state)
    bad = action.model_copy(update={'operation_id': 'offline-bad',
        'base_submission_digest': state['workpaper_draft']['digest']})
    bad = SaveWorkpaperEditsAction.model_validate_json(json.dumps({**bad.model_dump(mode='json'),
        'edits': [{'op': 'set_field', 'path': '/absent', 'value': 'invalid'}]}))
    try:
        save_draft(state, bad)
        raise AssertionError('bad batch must fail')
    except WorkpaperEditError as exc:
        append('offline-bad', 'SaveWorkpaperEditsAction', bad.model_dump(mode='json'),
               {'saved': False, 'error': str(exc)}, 'error')
    assert state == saved_state
    check(rows, 'after-local-error', wires[-1])
    final = FinalizeWorkpaperRevisionAction(action='finalize_workpaper_revision', context_digest='0'*64,
        reason_summary='OFFLINE VALIDATOR ONLY', draft_digest=state['workpaper_draft']['digest'])
    proposal = finalize_draft(state, final)
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=deny, evidence_tool=deny, finance_tool=deny, allow_workpaper_field_edits=True,
        authoring_enabled=bool(state.get('authoring_context')),
        enforce_case_route_requirements=state.get('task_context', {}).get('instruction_source') != 'current_user_research_request'))
    result = graph.nodes['validate_submission'].runnable.invoke({**state, 'pending_action': proposal.model_dump(mode='json')})
    assert not result.get('final_submission'), 'Fixture cannot resolve the real review finding'
    append('offline-final-rejected', 'FinalizeWorkpaperRevisionAction', final.model_dump(mode='json'),
           {'accepted': False, 'feedback': result['last_submission_attempt']['validation_issues']}, 'error')
    check(rows, 'after-final-rejection', wires[-1])
    # Material selection follows author progress, not elapsed tool count.
    keep = originals[:1]
    append('offline-select', 'UpdateResearchStateAction', {'retain_source_ids': [identity(keep[0])]}, {'accepted': True})
    v = check(rows, 'explicit-selection', wires[-1], keep)
    assert {identity(r) for r in v['current_materials']} == {identity(keep[0])}
    assert state['last_submission_attempt'] == old_attempt
    assert state['notebook']['observations'] == old_observations
    assert {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files} == hashes
    report = {'network_disabled': True, 'paid_calls': 0, 'financial_artifacts_promoted': 0,
        'original_files_unchanged': True, 'actual_request_count': 3, 'initial_materials': 7,
        'saved_batches_on_copies': 2, 'restart_after_save': True, 'bad_batch_preserves_prior_saves': True,
        'full_validation_still_rejects_unresolved_finding': True, 'readbacks_verified_each_stage': True,
        'original_observations_and_candidate_unchanged': True, 'stages': results, 'input_hashes': hashes}
    (args.output/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'stages','input_hashes'}}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('audit', 'wire-dir', 'state', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    with patch.object(socket.socket, 'connect', deny), patch('socket.create_connection', deny):
        run(parser.parse_args())
