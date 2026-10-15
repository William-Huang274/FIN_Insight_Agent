"""Replay an accepted author's revision request with network disabled.

Inputs are private native audit JSONL and the corresponding saved SDK wire.
Preserves the original pressure reminder, model, tools and limits. This checks
request assembly/readback, not model behavior, token cost or research quality.
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
from langchain_core.messages import SystemMessage
from pydantic import SecretStr
import jsonpointer

from replay_source_context import messages
from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek
from sec_agent.agent_runtime.research_context_view import (
    current_context, decode, material_ids, public_operation, working_view,
)


def encoded(value):
    return json.dumps(value, ensure_ascii=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def run(audit, wire_path, call_id, output):
    records = [json.loads(line) for line in audit.read_text(encoding='utf8').splitlines()]
    matches = [r for r in records if r.get('event') == 'request' and r.get('call_id') == call_id]
    assert len(matches) == 1, 'Select exactly one original canonical request'
    record = matches[0]
    original = messages(record)
    saved = deepcopy(original)
    old = json.loads(wire_path.read_text(encoding='utf8'))
    old_view = next(decode(m['content']) for m in old['messages']
                    if m['role'] == 'user' and 'current_materials' in decode(m['content']))
    # Keep the exact pressure notice that was actually sent, after the material
    # boundary. It is a runtime reminder, not a new research action.
    reminders = [m for m in old['messages'][1:] if m['role'] == 'system']
    projected_input = [*original, *[SystemMessage(content=m['content'],
        additional_kwargs={'fin_context_checkpoint_instruction': True}) for m in reminders]]
    chat = ReasoningPreservingChatDeepSeek(model=old['model'], api_key=SecretStr('offline'),
        tool_context_policy='task_boundary', max_retries=0, use_responses_api=False)
    sdk = chat._get_request_payload(projected_input, tools=old['tools'], tool_choice='auto')
    wire = {**old, 'messages': sdk['messages'], 'tools': sdk['tools']}
    view = next(decode(m['content']) for m in wire['messages']
                if m['role'] == 'user' and 'current_materials' in decode(m['content']))
    projected = working_view(projected_input)
    assert working_view(projected) == projected
    assert len(wire['messages']) == len(old['messages'])
    assert wire['messages'][0] == old['messages'][0]
    assert [m for m in wire['messages'][1:] if m['role'] == 'system'] == reminders
    assert wire['tools'] == old['tools']
    for key in ('current_materials', 'current_material_bindings', 'pending_state_proposal', 'material_focus'):
        assert view[key] == old_view[key], key
    c, before = view['current_context'], old_view['current_context']
    for key in ('submission_to_repair', 'execution_budget', 'allowed_actions'):
        assert c[key] == before[key], key
    task, old_task = c['task_context'], before['task_context']
    for key in ('research_question', 'revision_feedback', 'revision_instruction', 'research_working_state'):
        assert task.get(key) == old_task.get(key), key
    assert 'objective' not in c['branch']
    assert not {'authoring_context', 'authoring_instruction', 'task_scope', 'accepted_revision_baseline'} & task.keys()
    assert not {'objective', 'success_criteria'} & task['assignment'].keys()
    assert task['revision_task']['optional_updates'] == 'not_required_for_this_revision'
    reads = []
    raw_context = current_context(original)
    for name, read in task['research_background']['reads'].items():
        cid = read['arguments']['tool_call_id']
        result = public_operation(original, cid)
        expected = jsonpointer.resolve_pointer(raw_context, cid.removeprefix('runtime:context:'))
        assert result['receipt']['result'] == expected, name
        reads.append({'name': name, 'tool_call_id': cid, 'result_sha256': digest(expected)})
    assert len(view['operation_catalog']) == len(old_view['operation_catalog'])
    for new, previous in zip(view['operation_catalog'], old_view['operation_catalog']):
        assert {k: v for k, v in new.items() if k != 'source_ids'} == {
            k: v for k, v in previous.items() if k != 'purpose'}
        assert 'purpose' not in new
        cid = new['tool_call_id']
        result = public_operation(original, cid)
        assert result is not None, cid
        assert result == public_operation(saved, cid), cid
        reads.append({'tool_call_id': cid, 'result_sha256': digest(result)})
    assert original == saved, 'Never mutate canonical history'
    report = {
        'paid_calls': 0, 'network_disabled': True, 'call_id': call_id,
        'audit_record_sha256': digest(record), 'original_wire_sha256': digest(old),
        'before_sdk_characters': len(encoded(old)), 'after_sdk_characters': len(encoded(wire)),
        'material_count': len(view['current_materials']),
        'material_ids': sorted(material_ids(view['current_materials'])),
        'materials_and_bindings_exact': True, 'candidate_exact': True, 'active_feedback_exact': True,
        'permissions_and_budget_exact': True, 'pressure_notice_exact': True,
        'old_task_guidance_retired': True, 'historical_action_purposes_retired': True,
        'canonical_history_unchanged': True, 'idempotent': True, 'readbacks': reads,
        'limits': 'Offline request/readback verification only; no observed author behavior or token savings.',
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / 'request.private.json').write_text(encoded(wire), encoding='utf8')
    (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(encoded({k: v for k, v in report.items() if k != 'readbacks'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--wire', type=Path, required=True)
    parser.add_argument('--call-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Offline replay forbids network')):
        run(args.audit, args.wire, args.call_id, args.output)
