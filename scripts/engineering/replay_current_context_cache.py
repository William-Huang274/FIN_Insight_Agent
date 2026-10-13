"""Offline exact-duplicate/prefix audit of a same-author saved request sequence.

Supply private native audit JSONL and request-N.private.json.gz SDK payloads.
No model/source calls; sockets are disabled. Character counts are not tokens or
provider cache measurements. Original request envelopes and source data persist.
"""
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
import socket
from unittest.mock import patch

import jsonpointer
from pydantic import SecretStr

from replay_source_context import messages
from sec_agent.agent_runtime.deepseek_structured_agents import (
    ReasoningPreservingChatDeepSeek, _NATIVE_SPECIALIST_TOOLS, _native_function_schema,
    specialist_tools_for_actions, ordered_specialist_tools,
)
from sec_agent.agent_runtime.model_context import project_tool_history, research_checkpoint_request
from sec_agent.agent_runtime.research_context_view import decode, current_context, public_operation


def encoded(value):
    return json.dumps(value, ensure_ascii=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def expand(value, view, pointers):
    if isinstance(value, dict):
        if set(value) == {'current_value_at'}:
            target = jsonpointer.resolve_pointer(view, value['current_value_at'])
            assert not (isinstance(target, dict) and 'current_value_at' in target), 'No alias chains'
            pointers.append(value['current_value_at'])
            return deepcopy(target)
        return {k: expand(v, view, pointers) for k, v in value.items()}
    if isinstance(value, list):
        return [expand(v, view, pointers) for v in value]
    return value


def run(audit, wire_dir, output):
    records = [r for line in audit.open(encoding='utf8') if (r := json.loads(line)).get('raw_response')]
    assert records and len({r['actor'] for r in records}) == 1, 'Use one author sequence'
    output.mkdir(parents=True, exist_ok=True)
    chat = ReasoningPreservingChatDeepSeek(model='deepseek-v4-flash', api_key=SecretStr('offline'),
        tool_context_policy='task_boundary', research_checkpoint_tokens=48000, max_retries=0, use_responses_api=False)
    stable_system = messages(records[0])[0]
    assert stable_system.type == 'system' and 'now writing your own scoped' not in stable_system.content
    results, wires, old_wires = [], [], []
    for n, record in enumerate(records, 1):
        with gzip.open(wire_dir / f'request-{n}.private.json.gz', 'rt', encoding='utf8') as f:
            old = json.load(f)
        original = messages(record); saved = deepcopy(original); projected_input = deepcopy(original)
        # Same-author system is built once; the real adapter has a mock-transport
        # regression covering research -> authoring -> research with this policy.
        assert (original[0].content == stable_system.content
                or 'now writing your own scoped workpaper' in original[0].content)
        projected_input[0] = deepcopy(stable_system)
        context = current_context(projected_input)
        native = specialist_tools_for_actions(_NATIVE_SPECIALIST_TOOLS, context['allowed_actions'])
        from sec_agent.agent_runtime.working_memory_tools import WORKING_MEMORY_MODELS
        names = {x.get('function', x)['name'] for x in old['tools']}
        native.update({k: v for k, v in WORKING_MEMORY_MODELS.items() if k in names})
        native = ordered_specialist_tools(native)
        projected_input = [m for m in projected_input if not m.additional_kwargs.get('fin_context_checkpoint_instruction')]
        projected_input, native, _ = research_checkpoint_request(projected_input, model=chat,
            native_tools=native, runtime_context_binding=True, schema=_native_function_schema, max_input_characters=850000)
        schemas = [_native_function_schema(t, runtime_context_binding=True) for t in native.values()]
        sdk = chat._get_request_payload(projected_input, tools=schemas, tool_choice='auto')
        # Retain the originally recorded model/profile/limits verbatim.
        wire = {**old, 'messages': sdk['messages'], 'tools': sdk['tools']}
        old_tools = {x.get('function', x)['name']: x for x in old['tools']}
        new_tools = {x.get('function', x)['name']: x for x in wire['tools']}
        assert old_tools == new_tools, 'No tool added, lost, or schema changed'
        final = project_tool_history(projected_input, policy='task_boundary')
        assert final == project_tool_history(final, policy='task_boundary')
        view = next(decode(m.content) for m in final if m.additional_kwargs.get('fin_research_working_view'))
        old_view = next(decode(m['content']) for m in old['messages']
                        if m['role'] == 'user' and 'current_materials' in decode(m['content']))
        for key in ('current_materials', 'current_material_bindings', 'pending_state_proposal'):
            assert view[key] == old_view[key], key
        pointers = []
        task = expand(view['current_context']['task_context'], view, pointers)
        expected = old_view['current_context']['task_context']
        assert task == expected, (n,
            [k for k in set(task) | set(expected) if task.get(k) != expected.get(k)],
            sorted(set(task) - set(expected)), sorted(set(expected) - set(task)))
        source_calls = {c['id']: c for m in original if m.type == 'ai' for c in m.tool_calls}
        readbacks = []
        for m in final:
            if m.type == 'ai':
                old_m = next(x for x in original if x.type == 'ai' and x.tool_calls == [source_calls[c['id']] for c in m.tool_calls])
                assert m.additional_kwargs == old_m.additional_kwargs and m.content == old_m.content
                for c in m.tool_calls:
                    assert expand(c['args'], view, pointers) == source_calls[c['id']]['args']
            if m.type == 'tool':
                old_m = next(x for x in original if x.type == 'tool' and x.tool_call_id == m.tool_call_id)
                body = decode(old_m.content); body.pop('current_context', None)
                assert expand(decode(m.content), view, pointers) == body
                assert m.status == old_m.status
        ids = [item['tool_call_id'] for item in view['operation_catalog']]
        ids += [m.tool_call_id for m in final if m.type == 'tool']
        for cid in ids:
            operation = public_operation(original, cid)
            assert operation is not None, cid
            readbacks.append({'id': cid, 'sha256': digest(operation)})
        assert saved == original, 'Canonical journal mutated'
        with gzip.open(output / f'request-{n}.private.json.gz', 'wt', encoding='utf8') as f:
            json.dump(wire, f, ensure_ascii=False)
        results.append({'request': n, 'original_record_sha256': digest(record),
            'before_characters': len(encoded(old)), 'after_characters': len(encoded(wire)),
            'saved_characters': len(encoded(old)) - len(encoded(wire)),
            'exact_aliases': len(pointers), 'readbacks': readbacks,
            'material_sha256': digest(view['current_materials']),
            'task_equal_after_alias_resolution': True, 'tool_schema_sets_equal': True,
            'original_journal_unchanged': True})
        wires.append(wire); old_wires.append(old)
    pairs = []
    for i in range(1, len(wires)):
        def user(w):
            return next(m['content'] for m in w['messages'] if m['role'] == 'user')
        pairs.append({'requests': [i, i + 1],
            'old_user_prefix_characters': len(os.path.commonprefix([user(old_wires[i-1]), user(old_wires[i])])),
            'new_user_prefix_characters': len(os.path.commonprefix([user(wires[i-1]), user(wires[i])])),
            'new_system_equal': wires[i-1]['messages'][0] == wires[i]['messages'][0],
            'new_tools_equal': wires[i-1]['tools'] == wires[i]['tools'],
            'old_tool_prefix_characters': len(os.path.commonprefix([encoded(old_wires[i-1]['tools']), encoded(old_wires[i]['tools'])])),
            'new_tool_prefix_characters': len(os.path.commonprefix([encoded(wires[i-1]['tools']), encoded(wires[i]['tools'])]))})
    report = {'paid_calls': 0, 'rows': results, 'prefix_pairs': pairs,
              'limits': ['Fixed historical replay, not observed model behavior.',
                         'Characters/common prefix are not provider token usage or cache hit rate.',
                         'Legitimate stage menu changes remain; provider serialization is not visible.']}
    (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(encoded({'rows': [{k: v for k, v in r.items() if k != 'readbacks'} for r in results], 'prefix_pairs': pairs}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--wire-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Offline replay forbids network')):
        run(args.audit, args.wire_dir, args.output)
