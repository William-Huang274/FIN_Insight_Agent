"""Offline public-material and locator checks over indexed native requests.

No model invocation, source retrieval or network. Supply private audit indexes
and the previous replay.json; only hashes/counts/locations go in the output.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import socket
from unittest.mock import patch

from replay_source_context import digest, encoded, load_requests, messages
from sec_agent.agent_runtime.model_context import project_tool_history, research_checkpoint_request


def decode(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            if value.startswith('[Older read result omitted') and '\n{' in value:
                return json.loads(value.split('\n', 1)[1])
    return value


def walk(value, path=''):
    decoded = decode(value)
    if decoded is not value:
        yield from walk(decoded, path)
    elif isinstance(value, dict):
        yield path, value
        for k, child in value.items():
            yield from walk(child, f'{path}.{k}' if path else k)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk(child, f'{path}[{i}]')


def source_inventory(payload):
    passages, facts = {}, {}
    for _, row in walk(payload):
        if row.get('result_state') == 'source_bound_passage' and isinstance(row.get('passage'), str):
            passages[(row.get('passage_id'), digest(row))] = len(row['passage'])
        if row.get('schema_version') == 'fin_ia_numeric_fact_v1_0':
            facts[(row.get('numeric_fact_id'), digest(row))] = len(encoded(row))
    return passages, facts


def validate_locations(rows, original=None):
    """Dereference every context/source locator in the final request, not just JSON validity."""
    bodies = [decode(m.content) for m in rows]
    by_call = {getattr(m, 'tool_call_id', None) or (b.get('tool_call_id') if isinstance(b, dict) else None): i
        for i, (m, b) in enumerate(zip(rows, bodies))}
    count = 0
    keys = {'identical_snapshot_retained_at', 'identical_source_row_at', 'current_state_at', 'current_candidate_at'}
    def resolve(pointer, visited=()):
        index = pointer.get('message_index', by_call.get(pointer.get('tool_call_id')))
        field = pointer['field']
        identity = (index, field)
        assert identity not in visited, ('cyclic locator', identity)
        assert isinstance(index, int) and 0 <= index < len(rows), ('missing message', pointer)
        value = bodies[index]
        if field.startswith('tool_calls') and hasattr(rows[index], 'tool_calls'):
            value = {'tool_calls': rows[index].tool_calls}
        for token in re.findall(r'[^.\[\]]+', field):
            while isinstance(value, dict) and keys.intersection(value):
                value = resolve(value[next(iter(keys.intersection(value)))], (*visited, identity))
            value = value[int(token)] if isinstance(value, list) else value[token]
        if isinstance(value, dict) and keys.intersection(value):
            value = resolve(value[next(iter(keys.intersection(value)))], (*visited, identity))
        return value
    for index, body in enumerate(bodies):
        for path, item in walk(body):
            for key in keys.intersection(item):
                if not isinstance(item[key], dict) or 'field' not in item[key]:
                    continue  # Schema/notice text is not a runtime locator.
                assert resolve(item[key]) is not None, (index, path, key)
                count += 1
    if original:
        # The current question, assignment, working note and pending update
        # must survive the same request projection, not merely exist in logs.
        for index in range(len(original) - 1, -1, -1):
            body = decode(original[index].content)
            if not isinstance(body, dict):
                continue
            context = body.get('current_context', body if original[index].type == 'human' else {})
            task = context.get('task_context') if isinstance(context, dict) else None
            if not isinstance(task, dict):
                continue
            prefix = 'current_context.' if 'current_context' in body else ''
            for key in ('research_question', 'assignment', 'dependency_workpapers', 'delegated_work',
                        'research_working_state', 'pending_working_state_update'):
                if key in task:
                    assert resolve({'message_index': index, 'field': prefix + 'task_context.' + key}) == task[key], ('current task changed', key)
            break
    return count


def run(baseline_path, payload_dir):
    from pydantic import SecretStr
    from sec_agent.agent_runtime.deepseek_structured_agents import (
        ReasoningPreservingChatDeepSeek, _NATIVE_SPECIALIST_TOOLS, _native_function_schema)
    from sec_agent.agent_runtime.research_working_state import UpdateResearchStateAction
    baseline = json.loads(baseline_path.read_text('utf-8'))
    selected = [dict(request_file=b['file'], request_line=b['line'], call_id=b['call_id']) for b in baseline['basis']]
    records = load_requests(selected)
    chat = ReasoningPreservingChatDeepSeek(model='deepseek-v4-flash', api_key=SecretStr('offline-fixture'),
        tool_context_policy='task_boundary', research_checkpoint_tokens=48000, max_retries=0, use_responses_api=False)
    native = {**_NATIVE_SPECIALIST_TOOLS, 'UpdateResearchStateAction': UpdateResearchStateAction}
    schemas = [_native_function_schema(t, runtime_context_binding=True) for t in native.values()]
    result = []
    for basis in baseline['basis']:
        n = basis['round']
        record = records[basis['call_id']]
        assert digest(record) == basis['record_digest']
        original = messages(record)
        saved = deepcopy(original)
        prepared, tools, notice = research_checkpoint_request(original, model=chat, native_tools=native,
            runtime_context_binding=True, schema=_native_function_schema, max_input_characters=2000000)
        final = project_tool_history(prepared, policy='task_boundary')
        assert original == saved and set(tools) == set(native)
        assert final == project_tool_history(final, policy='task_boundary'), f'projection idempotence round {n}'
        payload = chat._get_request_payload(prepared, tools=schemas, tool_choice='auto')
        assert payload == chat._get_request_payload(final, tools=schemas, tool_choice='auto')
        location_count = validate_locations(final, original)
        old = json.loads((payload_dir / f'r{n}.payload.private.json').read_text('utf-8'))
        old_passages, old_facts = source_inventory(old)
        passages, facts = source_inventory(payload)
        assert old_passages.keys() <= passages.keys(), ('retained source changed', n, old_passages.keys() - passages.keys())
        assert old_facts.keys() <= facts.keys(), ('retained numeric fact changed', n)
        native_calls = {c['id'] for m in final if m.type == 'ai' for c in [*m.tool_calls, *m.invalid_tool_calls]}
        original_calls = {c['id'] for m in original if m.type == 'ai' for c in [*m.tool_calls, *m.invalid_tool_calls]}
        assert all(m.tool_call_id in native_calls for m in final if m.type == 'tool' and m.tool_call_id in original_calls)
        calls = {c['id']: c for m in original if m.type == 'ai' for c in m.tool_calls}
        receipts = {m.tool_call_id: m for m in original if m.type == 'tool'}
        recoveries = []
        for _, recovery in walk(payload):
            if 'original_tool_call_id' not in recovery or not recovery.get('read_tool'):
                continue
            cid = recovery['original_tool_call_id']
            call = calls[cid]
            args = {k: v for k, v in call['args'].items() if k != 'context_digest'}
            if call['name'] == 'ReadDelegatedWorkAction' and 'section' not in args:
                body = decode(receipts[cid].content)
                args['section'] = body.get('result', body).get('delegated_view', 'workpaper')
            assert recovery['read_tool'] == call['name'] and recovery['arguments'] == args
            recoveries.append({'call_id': cid, 'saved_result_digest': digest(receipts[cid].content)})
        before, after = len(encoded(old)), len(encoded(payload))
        result.append({'round': n, 'before_characters': before, 'after_characters': after,
            'reduction_percent': round((before - after) / before * 100, 2), 'locations_resolved': location_count,
            'retained_passages': len(passages), 'passage_text_characters': sum(passages.values()),
            'retained_numeric_facts': len(facts), 'numeric_fact_characters': sum(facts.values()),
            'recovery_routes': recoveries, 'same_retained_material_hashes': True, 'archive_unchanged': True,
            'current_task_state_and_pending_update_preserved': True,
            'projection_idempotent': True, 'native_pairs_intact': True, 'advisory_remaining': notice is not None,
            'tools_characters': len(encoded(payload['tools'])),
            'active_reasoning_characters': sum(len(m.get('reasoning_content', '')) for m in payload['messages'])})
    return {'schema': 'offline_context_retirement.v1', 'network_calls': 0, 'rounds': result,
        'basis': baseline['basis'], 'limits': ['Frozen historical requests, not future model behavior.',
            'Recovery replay checks saved call arguments/results; no external reader was invoked.',
            'Character reduction is not measured provider token or monetary savings.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--baseline-payload-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def deny(*unused, **kwargs):
        raise RuntimeError('Network forbidden in offline replay')
    with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), patch.object(socket, 'create_connection', deny):
        report = run(args.baseline, args.baseline_payload_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print(encoded({'network_calls': 0, 'rounds': [{k: v for k, v in row.items() if k != 'recovery_routes'} for row in report['rounds']]}))


if __name__ == '__main__':
    main()
