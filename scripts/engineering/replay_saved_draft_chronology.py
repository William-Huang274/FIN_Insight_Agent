"""Offline replay of the canonical request immediately after a saved batch.

Only the request projection is rebuilt. The later failed model proposal is
diagnostic input, never repaired or executed. All private artifacts stay local.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from pydantic import SecretStr
from replay_source_context import messages
from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek
from sec_agent.agent_runtime.research_context_view import (
    current_context, public_operation, working_view,
)


def run(event_path, wire_path, state_path, accepted_event_path, output):
    paths = (event_path, wire_path, state_path, accepted_event_path)
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    event, old, state, accepted_event = [json.loads(p.read_text(encoding='utf8')) for p in paths]
    original = messages(event)
    immutable = deepcopy(original)
    # The audit's messages are BEFORE the failed response, not the response itself.
    assert event['messages_basis'] == 'original_history_before_sdk_request_projection'
    assert not any(m.invalid_tool_calls for m in original if m.type == 'ai')
    projected = working_view(original)
    assert working_view(projected) == projected
    chat = ReasoningPreservingChatDeepSeek(model=old['model'], api_key=SecretStr('offline'),
        tool_context_policy='task_boundary', max_retries=0, use_responses_api=False)
    sdk = chat._get_request_payload(original, tools=old['tools'], tool_choice=old['tool_choice'])
    wire = {**old, 'messages': sdk['messages'], 'tools': sdk['tools']}

    def view(w):
        return next(json.loads(m['content']) for m in w['messages'] if m['role'] == 'user'
                    and isinstance(m['content'], str) and '"current_materials"' in m['content'])

    previous, current = view(old), view(wire)
    # A temporal fix, not a new research prompt, altered manuscript or curation.
    assert current == previous
    assert {k: v for k, v in wire.items() if k != 'messages'} == {
        k: v for k, v in old.items() if k != 'messages'}
    assert wire['messages'][0] == old['messages'][0]
    assert wire['messages'][1:-1] == old['messages'][2:]
    assert wire['messages'][-1] == old['messages'][1]
    assert [m['role'] for m in wire['messages']][1:-1] == ['assistant', 'tool', 'tool']
    calls = wire['messages'][1]['tool_calls']
    assert [c['id'] for c in calls] == [m['tool_call_id'] for m in wire['messages'][2:-1]]
    save_call = next(c for c in calls if c['function']['name'] == 'SaveWorkpaperEditsAction')
    args = json.loads(save_call['function']['arguments'])
    saved = public_operation(original, save_call['id'])['receipt']['result']['draft_result']
    assert saved['saved'] and not saved.get('replayed', False) and not saved['submitted']
    assert saved['operation_id'] == args['operation_id']
    assert saved['draft_digest'] != args['base_submission_digest']
    assert saved['draft_digest'] == state['workpaper_draft']['digest']
    assert state['workpaper_draft']['saved_batches'] == 1
    output.mkdir(parents=True, exist_ok=True)
    # Exercise the real restart selector with BOTH responses present. It must
    # follow the accepted model receipt, not the newest failed response.
    from sec_agent.agent_runtime.author_revision import restore_author_history, author_continuation_options
    audit = output / 'restore-audit.private.jsonl'
    audit.write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in (event, accepted_event)) + '\n', encoding='utf8')
    adapter = SimpleNamespace(_agentic_history={})
    restore_author_history(adapter, state, [audit])
    restored = adapter._agentic_history[state['agent_id']]
    assert restored[-1].tool_calls == messages({'messages': [accepted_event['raw_response']]})[0].tool_calls
    assert not restored[-1].invalid_tool_calls
    assert [c['id'] for c in restored[-1].tool_calls] == [c['id'] for c in calls]
    continuation = author_continuation_options({'recovery_state': state,
        'research_task': state['task'], 'remaining_model_requests': lambda: 1}, state,
        authorized_model_requests=1)
    assert continuation['recovery_state']['max_model_turns'] == state['notebook']['model_turn_count'] + 1
    assert current['current_context']['submission_to_repair']['base_submission_digest'] == saved['draft_digest']
    raw_context = current_context(original)
    assert raw_context['submission_to_repair']['candidate'] == state['workpaper_draft']['arguments']
    readbacks = []
    for row in current['operation_catalog']:
        cid = row['tool_call_id']
        assert public_operation(original, cid) is not None, cid
        readbacks.append(cid)
    assert public_operation(original, 'runtime:context:/submission_to_repair/candidate') is not None
    assert original == immutable
    assert hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    invalid = event['raw_response']['invalid_tool_calls']
    assert len(invalid) == 1 and invalid[0]['name'] == 'SaveWorkpaperEditsAction'
    try:
        json.loads(invalid[0]['args'])
    except json.JSONDecodeError as exc:
        failure = {'message': exc.msg, 'line': exc.lineno, 'column': exc.colno, 'position': exc.pos,
                   'arguments_sha256': hashlib.sha256(invalid[0]['args'].encode()).hexdigest()}
    else:
        raise AssertionError('Expected the original malformed proposal, not a repaired copy')
    (output / 'request.private.json').write_text(json.dumps(wire, ensure_ascii=False), encoding='utf8')
    result = {'passed': True, 'provider_calls': 0, 'remaining_call_budget_consumed': 0,
        'state_and_failed_proposal_untouched': True, 'input_hashes': hashes,
        'roles_before': [m['role'] for m in old['messages']],
        'roles_after': [m['role'] for m in wire['messages']],
        'same_task_tools_materials_reasoning_and_receipts': True,
        'restore_selects_successful_call_before_failure': True,
        'one_call_limit_alignment_checked_offline': True,
        'current_materials': len(current['current_materials']),
        'observations': len(state['notebook']['observations']),
        'recovery_checks': len(state['task_context'].get('tool_recovery_checks', [])),
        'saved_batches': 1, 'draft_digest': saved['draft_digest'],
        'readback_entries_verified': len(readbacks), 'original_json_error': failure,
        'model_behavior_validated': False}
    (output / 'validation-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('event', 'wire', 'state', 'accepted-event', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Offline replay forbids network')):
        print(json.dumps(run(a.event, a.wire, a.state, a.accepted_event, a.output), ensure_ascii=False))
