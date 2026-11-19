"""Explicit author dismissal over native archives, for live and restored inputs.

Only successful, recoverable reads made BEFORE the release are projected away.
Re-reading is always visible; no model prose is interpreted as a release command.
"""
from copy import deepcopy
import json
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def release_history(messages):
    from .model_context import REREADABLE_TOOLS, _literal_reference_ids
    releasable = REREADABLE_TOOLS | {'RequestCalculationAction'}
    bodies = {}
    releases = []
    calls = {c['id']: c for m in messages if isinstance(m, AIMessage) for c in m.tool_calls}
    for index, message in enumerate(messages):
        if not isinstance(message, (HumanMessage, ToolMessage)) or not isinstance(message.content, str):
            continue
        try:
            body = json.loads(message.content)
        except (ValueError, TypeError):
            continue
        if not isinstance(body, dict):
            continue
        bodies[index] = body
        if isinstance(message, ToolMessage) and message.name == 'UpdateResearchStateAction' and message.status != 'error':
            result = body.get('result', body)
            if isinstance(result, dict) and result.get('context_release'):
                releases.append((index, result['context_release']))
        # Only the original restored task context; repeated live context copies
        # do not extend the lifetime of a release to newly read results.
        if isinstance(message, HumanMessage):
            task = body.get('task_context', {})
            if isinstance(task, dict):
                releases.extend((index, r) for r in task.get('context_releases', []))
    if not releases:
        return messages
    projected = deepcopy(list(messages))
    for index, body in bodies.items():
        message = messages[index]
        containers = []
        if isinstance(message, HumanMessage) and isinstance(body.get('progress'), dict):
            containers.append((body['progress'], True))
        context = body.get('current_context')
        if isinstance(message, ToolMessage) and isinstance(context, dict) and isinstance(context.get('progress'), dict):
            containers.append((context['progress'], True))
        if isinstance(message, ToolMessage) and message.name in releasable and message.status != 'error':
            result = body.get('result', body)
            if isinstance(result, dict) and not result.get('failure') and not result.get('error'):
                containers.append((result, False))
        changed = False
        for container, restored in containers:
            for obs in container.get('observations', []):
                if not isinstance(obs, dict) or obs.get('status') != 'success' or obs.get('failure') or obs.get('kind') not in {'evidence', 'finance'}:
                    continue
                recovery = obs.get('recovery')
                if isinstance(message, ToolMessage) and not restored:
                    call = calls.get(message.tool_call_id)
                    if not call:
                        continue
                    args = {k: v for k, v in call['args'].items() if k != 'context_digest'}
                    recovery = {'read_tool': call['name'], 'arguments': args, 'original_tool_call_id': message.tool_call_id}
                if not isinstance(recovery, dict) or not recovery.get('arguments') or recovery.get('read_tool') not in releasable:
                    continue
                selected = set()
                for boundary, release in releases:
                    eligible = index < boundary
                    if restored:
                        turn = recovery.get('batch_turn')
                        eligible = type(turn) is int and turn <= release.get('through_model_turn', -1)
                    if eligible:
                        selected.update(release.get('source_ids', []))
                if not selected:
                    continue
                for i, row in enumerate(obs.get('content', [])):
                    if not isinstance(row, dict) or row.get('result_state') not in {'retrieval_candidate', 'source_bound_passage', 'numeric_fact', 'non_authoritative_metric'}:
                        continue
                    if row.get('company_section') == 'sources' and isinstance(row.get('sources'), list) and row.get('entity_id') not in selected:
                        for j, source in enumerate(row['sources']):
                            if not isinstance(source, dict):
                                continue
                            ids = _literal_reference_ids(source, include_navigation=True)
                            if selected.intersection(ids):
                                row['sources'][j] = {'result_state': 'released_navigation',
                                    'observed_reference_ids': ids, 'recovery': recovery,
                                    'notice': 'Author dismissed this file card; exact original remains recoverable.'}
                                changed = True
                        continue
                    ids = _literal_reference_ids(row, include_navigation=True)
                    if not selected.intersection(ids):
                        continue
                    obs['content'][i] = {'result_state': 'released_navigation',
                        'observed_reference_ids': ids, 'recovery': recovery,
                        'notice': 'Author dismissed this consumed result. Original preserved, not evidence here. Repeat read_tool/arguments with current binding to recover; newer reads stay visible.'}
                    changed = True
        if changed:
            projected[index].content = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
    return projected
