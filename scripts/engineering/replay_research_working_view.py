"""Replay indexed native research requests and their actual offline history reader.

Never invokes a provider. Private input indexes and optional payloads belong
outside Git. Counts are serialized SDK characters, not provider tokens.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import socket
from unittest.mock import patch

from replay_source_context import digest, encoded, load_requests, messages
from replay_context_retirement import source_inventory, walk
from replay_current_context_cache import expand
from sec_agent.agent_runtime.research_context_view import decode, compact_current_context, current_context
from sec_agent.agent_runtime.research_context_view import INITIAL_CONTEXT_ID
from sec_agent.agent_runtime.source_result_view import source_message_views, source_result_view
from langchain_core.messages import ToolMessage
from sec_agent.agent_runtime.model_context import project_tool_history, research_checkpoint_request


def wire_components(payload):
    """Additive SDK character allocation, including escaped JSON and wrappers."""
    parts={'tools':len(encoded(payload['tools']))}
    for original in payload['messages']:
        message=deepcopy(original); body=decode(message.get('content'))
        if isinstance(body,dict) and 'operation_catalog' in body:
            for key in list(body):
                before=len(encoded(message));body.pop(key)
                message['content']=json.dumps(body,ensure_ascii=False,separators=(',',':'))
                parts[key]=before-len(encoded(message))
            parts['working_view_envelope']=len(encoded(message))
        else:
            key=message['role'];parts[key]=parts.get(key,0)+len(encoded(message))
    parts['outer_serialization']=len(encoded(payload))-sum(parts.values())
    return parts


def run(baseline_path, payload_dir, output_dir):
    from pydantic import SecretStr
    from sec_agent.agent_runtime.deepseek_structured_agents import (
        DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek,
        _NATIVE_SPECIALIST_TOOLS, _native_function_schema, specialist_tools_for_actions)
    from sec_agent.agent_runtime.research_working_state import UpdateResearchStateAction
    baseline = json.loads(baseline_path.read_text('utf-8'))
    records = load_requests([dict(request_file=b['file'], request_line=b['line'], call_id=b['call_id'])
                             for b in baseline['basis']])
    chat = ReasoningPreservingChatDeepSeek(model='deepseek-v4-flash', api_key=SecretStr('offline-fixture'),
        tool_context_policy='task_boundary', research_checkpoint_tokens=48000, max_retries=0, use_responses_api=False)
    adapter = object.__new__(DeepSeekStructuredAgentAdapter)
    results = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for basis in baseline['basis']:
        n = basis['round']; record = records[basis['call_id']]
        assert digest(record) == basis['record_digest']
        original = messages(record); saved = deepcopy(original)
        native = specialist_tools_for_actions({**_NATIVE_SPECIALIST_TOOLS, 'UpdateResearchStateAction': UpdateResearchStateAction},
                                               current_context(original)['allowed_actions'])
        schemas = [_native_function_schema(t, runtime_context_binding=True) for t in native.values()]
        adapter._agentic_history = {record['actor']: original}
        final = project_tool_history(original, policy='task_boundary')
        assert original == saved and project_tool_history(final, policy='task_boundary') == final
        view = next(decode(m.content) for m in final if m.additional_kwargs.get('fin_research_working_view'))
        # Current draft, full latest native reasoning and its errors stay exact;
        # only the replicated host snapshot moves into the single current view.
        last_ai = max(i for i, m in enumerate(original) if m.type == 'ai')
        expected = deepcopy(original[last_ai:])
        for m in expected:
            if m.type == 'tool' and isinstance(b := decode(m.content), dict) and 'current_context' in b:
                del b['current_context']; m.content = json.dumps(b, ensure_ascii=False, separators=(',', ':'))
        resolved = deepcopy(final[-len(expected):])
        for m in resolved:
            if isinstance(b := decode(m.content), dict):
                m.content = json.dumps(expand(b, view, []), ensure_ascii=False, separators=(',', ':'))
            if m.type == 'ai':
                for call in m.tool_calls:
                    call['args'] = expand(call['args'], view, [])
        for m in expected:
            if isinstance(b := decode(m.content), dict):
                m.content = json.dumps(b, ensure_ascii=False, separators=(',', ':'))
        assert resolved == expected
        # Exact task/assignment semantics, independent of changed message positions.
        contexts = [b.get('current_context', b if m.type == 'human' else {}) for m in original
                    if isinstance(b := decode(m.content), dict)]
        latest = next(c for c in reversed(contexts) if isinstance(c, dict) and 'task_context' in c)
        for key in ('research_question', 'assignment', 'dependency_workpapers', 'delegated_work', 'pending_working_state_update'):
            if key in latest['task_context']:
                assert view['current_context']['task_context'][key] == compact_current_context(latest)['task_context'][key], key
        note = latest['task_context'].get('research_working_state')
        if isinstance(note, dict):
            assert view['current_context']['task_context']['research_working_state'] == {k:v for k,v in note.items() if k != 'reference_issues'}
        recovered = []
        for item in view['operation_catalog']:
            cid = item['tool_call_id']
            returned = adapter.read_public_operation(record['actor'], cid)
            assert returned is not None and adapter.read_public_operation('unrelated-actor', cid) is None
            if cid == INITIAL_CONTEXT_ID:
                body = next(decode(m.content) for m in original if m.type == 'human' and isinstance(decode(m.content),dict) and 'task_context' in decode(m.content))
                assert returned['receipt']['result'] == body
                recovered.append(returned)
                continue
            receipt = next(m for m in original if m.type == 'tool' and m.tool_call_id == cid)
            body = decode(receipt.content); result = body.get('result', body) if isinstance(body, dict) else receipt.content
            if isinstance(result, dict):
                result = {k:v for k,v in result.items() if k != 'current_context'}
            assert returned['receipt']['result'] == result and returned['receipt']['status'] == receipt.status
            recovered.append(returned)
        assert adapter.read_public_operation(record['actor'], 'nonexistent') is None
        prepared, tools, notice = research_checkpoint_request(original, model=chat, native_tools=native,
            runtime_context_binding=True, schema=_native_function_schema, max_input_characters=2000000)
        payload = chat._get_request_payload(prepared, tools=schemas, tool_choice='auto')
        assert set(tools) == set(native)
        old = json.loads((payload_dir / f'r{n}.payload.private.json').read_text('utf-8'))
        old['tools'] = [t for t in old['tools'] if t.get('name', t.get('function', {}).get('name')) in native]
        old_p, old_f = source_inventory(old); hot_p, hot_f = source_inventory(payload)
        # Saved originals remain exact. Also compare the maintained source
        # metadata view used by the previous replay, which removes only repeats.
        recovered_view = source_message_views([ToolMessage(content=json.dumps(r['receipt']['result'],ensure_ascii=False),tool_call_id=str(i)) for i,r in enumerate(recovered)])
        available_p, available_f = source_inventory([payload, recovered, [m.content for m in recovered_view]])
        assert old_p.keys() <= available_p.keys(), ('lost original passage', n, old_p.keys()-available_p.keys())
        assert old_f.keys() <= available_f.keys(), ('lost financial identity', n, old_f.keys()-available_f.keys())
        # Every explicit current pin must resolve to an unchanged typed object,
        # either in the working view or still in the active native batch.
        pin_calls = [c for m in original if m.type == 'ai' for c in m.tool_calls if c['name']=='UpdateResearchStateAction']
        pins = []
        if pin_calls:
            a=pin_calls[-1]['args']; pins=a.get('working_state', a).get('retain_source_ids', [])
        hot_ids = {r.get('passage_id') or r.get('numeric_fact_id') or r.get('calculation_id') for _,r in walk(payload)}
        raw_ids = {r.get('passage_id') or r.get('numeric_fact_id') or r.get('calculation_id') for m in original for _,r in walk(m.content)}
        assert (set(pins) & raw_ids) <= hot_ids, ('current material selection lost', n, (set(pins)&raw_ids)-hot_ids)
        def pinned_originals(values):
            return {digest(source_result_view(row)) for _,row in walk(values)
                    if (row.get('passage_id') or row.get('numeric_fact_id') or row.get('calculation_id')) in pins
                    and (isinstance(row.get('passage'),str) or 'value_decimal' in row)}
        assert pinned_originals([m.content for m in original]) <= pinned_originals(payload), ('current original changed', n)
        (output_dir/f'r{n}.payload.private.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8')
        before, after = len(encoded(old)), len(encoded(payload))
        results.append({'round':n,'before_characters':before,'after_characters':after,
            'reduction_percent':round((before-after)/before*100,2),
            'tools_characters':len(encoded(payload['tools'])),
            'wire_components':wire_components(payload),
            'working_view_components':{k:len(encoded(v)) for k,v in view.items()},
            'hot_passages':len(hot_p),'hot_numeric_facts':len(hot_f),
            'previous_passages_recoverable_exactly':len(old_p),'previous_numeric_facts_recoverable_exactly':len(old_f),
            'operation_receipts_read_back_exactly':len(recovered),'current_pins_observed':len(set(pins)&raw_ids),
            'current_pins_missing_in_original':sorted(set(pins)-raw_ids),
            'current_task_state_and_active_pair_preserved':True,'canonical_archive_unchanged':True,
            'current_pinned_original_hashes_preserved':True,
            'projection_idempotent':True,'advisory_remaining':notice is not None})
    return {'schema':'offline_research_working_view.v1','network_calls':0,'basis':baseline['basis'],'rounds':results,
        'limits':['Frozen requests and native reader replay; no live model/deployment.',
                  'Characters are not measured provider tokens or cost savings.',
                  'Hot materials and recoverable originals are reported separately.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--baseline-payload-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    def deny(*args,**kwargs): raise RuntimeError('Network forbidden in offline replay')
    with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny):
        report=run(a.baseline,a.baseline_payload_dir,a.output_dir)
    (a.output_dir/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(encoded({'network_calls':0,'rounds':report['rounds']}))


if __name__=='__main__': main()
