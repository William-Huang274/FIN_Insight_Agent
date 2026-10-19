"""Replay saved request/source/state boundaries without a model or network.

Input: an offline audit directory containing rounds.json and actions.private.json.
Those indexes point to immutable native request JSONL files; neither index nor
private source data is a repository/installation dependency. Outputs contain
diagnostics, not original prose or provider reasoning. No token/cost estimator.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch


# The developer virtualenv can have the primary checkout installed in editable
# mode.  This replay is deliberately runnable from an isolated worktree, so
# load the adjacent source tree before importing runtime modules.  Otherwise a
# replay can silently combine this script with a different checkout's runtime.
ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = str((ROOT / "src").resolve())
if SOURCE_ROOT not in sys.path:
    sys.path.insert(0, SOURCE_ROOT)

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from sec_agent.agent_runtime.model_context import project_tool_history, research_checkpoint_request
from sec_agent.agent_runtime.research_working_state import UpdateResearchStateAction, apply_working_state
from sec_agent.research_foundation.source_bound_calculator import (
    ObservedSourceRegistry, SourceBoundCalculation, calculate_from_sources,
)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def digest(value):
    return hashlib.sha256(encoded(value).encode('utf-8')).hexdigest()


def messages(record):
    classes = {'system': SystemMessage, 'human': HumanMessage, 'ai': AIMessage, 'tool': ToolMessage}
    return [classes[row['type']].model_validate(row) for row in record['messages']]


def load_requests(rows):
    wanted = {}
    for row in rows:
        wanted.setdefault(row['request_file'], {})[row['request_line']] = row
    loaded = {}
    for file, lines in wanted.items():
        with Path(file).open(encoding='utf-8') as stream:
            for line_number, line in enumerate(stream, 1):
                if line_number in lines:
                    record = json.loads(line)
                    row = lines[line_number]
                    if record['call_id'] != row['call_id']:
                        raise ValueError('Audit index/request call identity mismatch')
                    loaded[row['call_id']] = record
                if line_number >= max(lines):
                    break
    if len(loaded) != len(rows):
        raise ValueError('Missing indexed native requests')
    return loaded


def observations(rows):
    found = []
    for message in rows:
        if not isinstance(message, ToolMessage) or message.status == 'error':
            continue
        try:
            body = json.loads(message.content)
        except (TypeError, ValueError):
            continue
        body = body.get('result', body)
        if isinstance(body, dict):
            found.extend(body.get('source_observations', []))
            found.extend(body.get('observations', []))
    return found


def calculate(request, registry):
    def lookup(identity):
        item = registry.get(identity)
        if item is None:
            raise ValueError('source_id_not_observed_in_this_tool_session')
        return item
    try:
        result = calculate_from_sources(SourceBoundCalculation.model_validate(request), lookup)
        return {key: result[key] for key in ('value_decimal', 'result_unit', 'arithmetic_verified', 'financial_semantics_verified')}
    except ValueError as exc:
        return {'error': str(exc)}


def projection(rows):
    original = [m.model_dump(mode='json') for m in rows]
    result = project_tool_history(rows, policy='task_boundary')
    assert original == [m.model_dump(mode='json') for m in rows], 'Request archive mutated'
    assert result == project_tool_history(result, policy='task_boundary'), 'Projection not idempotent'
    # Completed native pairs may become human archive entries. Remaining tool
    # results must keep their assistant call; the original journal is untouched.
    calls = {c['id'] for m in result if isinstance(m, AIMessage) for c in m.tool_calls}
    original_calls = {c['id'] for m in rows if isinstance(m, AIMessage) for c in m.tool_calls}
    for message in result:
        if isinstance(message, ToolMessage) and message.tool_call_id in original_calls:
            assert message.tool_call_id in calls, 'Orphaned native tool result'
    return {'original_message_characters': len(encoded(original)),
            'projected_message_characters': len(encoded([m.model_dump(mode='json') for m in result])),
            'archive_unchanged': True, 'idempotent': True, 'no_new_orphaned_tool_results': True}


def working_window(record):
    """Production serializer + current specialist schemas; no invoke/transport."""
    from pydantic import SecretStr
    from sec_agent.agent_runtime.deepseek_structured_agents import (
        ReasoningPreservingChatDeepSeek, _native_function_schema, _NATIVE_SPECIALIST_TOOLS)
    chat = ReasoningPreservingChatDeepSeek(model='deepseek-v4-flash', api_key=SecretStr('offline-fixture'),
        tool_context_policy='task_boundary', research_checkpoint_tokens=48000,
        max_retries=0, use_responses_api=False)
    native = {**_NATIVE_SPECIALIST_TOOLS, 'UpdateResearchStateAction': UpdateResearchStateAction}
    schemas = [_native_function_schema(t, runtime_context_binding=True) for t in native.values()]
    rows = messages(record)
    before = len(encoded(chat._get_request_payload(rows, tools=schemas, tool_choice='auto')))
    projected, tools, notice = research_checkpoint_request(rows, model=chat, native_tools=native,
        runtime_context_binding=True, schema=_native_function_schema, max_input_characters=2000000)
    after = len(encoded(chat._get_request_payload(projected, tools=schemas, tool_choice='auto')))
    assert set(tools) == set(native), 'Research tools restricted by projection'
    return {'same_current_schema_before_characters': before, 'working_window_after_characters': after,
            'tools_unchanged': True, 'advisory_remaining': notice is not None,
            'profile': 'task_boundary / 48000 estimated-token trigger / 2000000 character ceiling',
            'basis': 'Offline current SDK payload serialization, not actual newly billed token usage'}


def run(audit_dir, actor):
    all_rounds = json.loads((audit_dir / 'rounds.json').read_text('utf-8'))
    all_actions = json.loads((audit_dir / 'actions.private.json').read_text('utf-8'))
    indexed = {r['actor_round']: r for r in all_rounds if r.get('actor') == actor}
    selected = [indexed[n] for n in (11, 15, 19, 20)]
    loaded = load_requests(selected)
    records = {n: loaded[indexed[n]['call_id']] for n in (11, 15, 19, 20)}
    actions = {r['actor_round']: r['actions'] for r in all_actions if r.get('actor') == actor}
    history = messages(records[15])
    direct = [m for m in history if not isinstance(m, ToolMessage) or m.name not in {
        'ReadDelegatedWorkAction', 'ReadDependencyWorkAction'}]
    handoffs = [m for m in history if isinstance(m, ToolMessage) and m.name in {
        'ReadDelegatedWorkAction', 'ReadDependencyWorkAction'}]
    before = ObservedSourceRegistry(observations(direct))
    after = ObservedSourceRegistry(observations(direct))
    handed = observations(handoffs)
    original_handoffs = digest(handed)
    after.restore(handed)
    calculations = []
    for action in actions[15]:
        if action['name'] != 'RequestCalculationAction':
            continue
        request = action['args']['request']
        calculations.append({'round': 15, 'tool_call_id': action['id'], 'request_digest': digest(request),
            'source_ids': sorted({op['source_id'] for op in request['operands'].values()}),
            'before': calculate(request, before), 'after': calculate(request, after),
            'all_sources_registered': all(after.get(op['source_id']) is not None for op in request['operands'].values())})
    assert digest(handed) == original_handoffs
    assert len(calculations) == 3 and all(c['all_sources_registered'] for c in calculations)
    notes = []
    for n in (19, 20):
        raw = next(a for a in actions[n] if a['name'] == 'UpdateResearchStateAction')
        args = deepcopy(raw['args'])
        args.setdefault('context_digest', '0' * 64)  # Host binds this field; no model/source changes.
        parsed = UpdateResearchStateAction.model_validate(args)
        submitted_state = args.get('working_state') or {k: v for k, v in args.items()
            if k in type(parsed.working_state).model_fields}
        pending = parsed.working_state.model_dump(mode='json', exclude_unset=True)
        assert pending == submitted_state, 'Pending draft content changed during normalization'
        prior = records[n]['semantic_input']['task_context']['research_working_state'] or {}
        saved, issues = apply_working_state(parsed.working_state, prior)
        assert saved['findings'] == parsed.working_state.model_dump(mode='json')['findings']
        assert saved['subtasks'] == prior.get('subtasks', []) and issues
        assert saved['phase_status'] == 'working'
        receipt = {'accepted': True, 'checkpoint': parsed.checkpoint, 'working_state': saved,
                   'update_issues': issues, 'subtask_batch_applied': False}
        # Same recorded history/action; replace only the host's response in a copy.
        # This is a counterfactual component replay, not a new model continuation.
        replay = messages(records[n]) + [AIMessage(content='', tool_calls=[{
            'name': raw['name'], 'id': raw['id'], 'args': raw['args'], 'type': 'tool_call'}]),
            ToolMessage(name=raw['name'], tool_call_id=raw['id'], content=encoded({'result': receipt}))]
        old = deepcopy(replay)
        old[-1].status = 'error'
        old[-1].content = encoded({'result': {'accepted': False, 'issues': issues}})
        notes.append({'round': n, 'tool_call_id': raw['id'], 'draft_digest': digest(raw['args']),
            'issues': issues, 'findings_saved': len(saved['findings']), 'prior_task_table_preserved': True,
            'pending_draft_preserved': True,
            'rejected_note_projection': projection(old), 'partial_acceptance_projection': projection(replay)})
    return {'schema': 'offline_source_context_replay.v1', 'actor': actor, 'network_calls': 0,
        'basis': [{'round': n, 'call_id': indexed[n]['call_id'], 'file': indexed[n]['request_file'],
                   'line': indexed[n]['request_line'], 'record_digest': digest(records[n])} for n in records],
        'calculations': calculations, 'notes': notes,
        'large_history_projection': {str(n): projection(messages(records[n])) for n in (11, 15)},
        'working_window': {str(n): working_window(records[n]) for n in (11, 15, 19, 20)},
        'limits': ['Recorded actions are replayed; future model decisions are not simulated.',
                   'Message characters are not provider tokens or a monetary saving estimate.',
                   'Arithmetic/identity checks do not establish financial comparability or correct research conclusions.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-dir', type=Path, required=True)
    parser.add_argument('--actor', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def deny_network(*unused, **kwargs):
        raise RuntimeError('Offline replay forbids network access')
    with patch.object(socket.socket, 'connect', deny_network), patch.object(socket.socket, 'connect_ex', deny_network), patch.object(socket, 'create_connection', deny_network):
        result = run(args.audit_dir, args.actor)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'calculations': result['calculations'], 'notes': result['notes'],
                      'large_history_projection': result['large_history_projection'], 'network_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
