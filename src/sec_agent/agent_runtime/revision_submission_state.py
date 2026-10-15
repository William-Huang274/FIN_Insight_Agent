"""Separate an unsubmitted revision from the accepted submission it revises."""
from copy import deepcopy
import json

from .research_graph_contracts import canonical_sha256


def starts_accepted_revision(request):
    """Host-validated first revision request, not a retry of a rejected draft."""
    status = request.get('revision_submission_status') or {}
    task = request.get('task_context') or {}
    baseline = task.get('accepted_revision_baseline') or {}
    turn = baseline.get('through_model_turn')
    return (status.get('status') == 'not_submitted' and status.get('baseline_accepted') is True
            and bool(task.get('revision_feedback')) and isinstance(turn, int)
            and (request.get('notebook') or {}).get('model_turn_count') == turn
            and bool(baseline.get('submission_digest'))
            and status.get('baseline_digest') == baseline['submission_digest'])


def accepted_baseline(state):
    baseline = (state.get('task_context') or {}).get('accepted_revision_baseline') or {}
    submission = baseline.get('submission')
    if not isinstance(submission, dict) or canonical_sha256(submission) != baseline.get('submission_digest'):
        return None
    return baseline


def revision_attempt_view(state):
    """Migrate old draft flags only when no revision submission actually occurred."""
    last = deepcopy(state.get('last_submission_attempt') or {})
    last.pop('submission_status', None)
    baseline = accepted_baseline(state)
    if not baseline or last.get('accepted') is True:
        return last
    if last.get('feedback') or last.get('validation_issues') or last.get('tool_call_id'):
        return last
    for record in state.get('notebook', {}).get('model_turn_records', []):
        if record['turn_index'] <= baseline['through_model_turn']:
            continue
        action = record.get('action') or {}
        if action.get('action') in {'submit_workpaper', 'revise_workpaper', 'submit_review'}:
            return last
        if any(c.get('name') in {'SubmitWorkpaperAction', 'ReviseWorkpaperAction', 'SubmitReviewAction'}
               for c in action.get('tool_calls', [])):
            return last
    if last.get('arguments'):
        last.update(accepted=None, submission_status='not_submitted')
    return last


def restore_accepted_receipt(messages, state, audit_paths):
    """Correct the known empty legacy false receipt in memory, using bound audit IDs.

    Raw audit files remain immutable. Neither a real validation rejection nor a
    later revision result is inferred from the accepted baseline.
    """
    baseline = accepted_baseline(state)
    if not baseline:
        return messages
    suspects = []
    for i, message in enumerate(messages):
        if message.type != 'tool' or message.name not in {'SubmitWorkpaperAction', 'ReviseWorkpaperAction'}:
            continue
        try:
            payload = json.loads(message.content)
        except (TypeError, ValueError):
            continue
        if payload.get('result') == {'accepted': False, 'feedback': [], 'validation_issues': []}:
            suspects.append((i, message, payload))
    if not suspects:
        return messages
    record = next((r for r in state.get('notebook', {}).get('model_turn_records', [])
                   if r['turn_index'] == baseline['through_model_turn']), None)
    if not record or record.get('context_digest') != baseline['submission'].get('context_digest'):
        return messages
    receipt = record.get('runtime_receipt') or {}
    if receipt.get('actor') != state.get('agent_id') or not receipt.get('request_digest'):
        return messages
    for path in audit_paths:
        if not path.is_file():
            continue
        with path.open(encoding='utf8') as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get('actor') != state['agent_id'] or event.get('request_digest') != receipt['request_digest']:
                    continue
                calls = (event.get('raw_response') or {}).get('tool_calls') or []
                if len(calls) != 1 or calls[0].get('name') not in {'SubmitWorkpaperAction', 'ReviseWorkpaperAction'}:
                    continue
                restored = list(messages)
                for i, message, payload in suspects:
                    if message.tool_call_id != calls[0]['id'] or message.name != calls[0]['name']:
                        continue
                    payload['result'] = {'accepted': True, 'feedback': [], 'validation_issues': [],
                        'restored_from_accepted_baseline': baseline['submission_digest']}
                    restored[i] = message.model_copy(update={'content': json.dumps(payload, ensure_ascii=False),
                                                            'status': 'success'})
                return restored
    return messages
