"""Version-bound lead decisions; saved tool receipts remain the source of truth."""
import json

from langchain_core.messages import ToolMessage
from .research_graph_contracts import canonical_sha256


def result_version(record):
    payload = {k: record.get(k) for k in ('request', 'opinion', 'assessment')}
    if 'workpaper_ref' in record:
        payload['workpaper_ref'] = record['workpaper_ref']
    return canonical_sha256(payload)


def latest_decisions(messages):
    decisions = {}
    for m in messages:
        if isinstance(m, ToolMessage) and m.name == 'assess_research_result' and m.status == 'success':
            body = json.loads(m.content)
            if body.get('decision_recorded'):
                decisions[body['task_id']] = (body, m.tool_call_id)
    return decisions


def workpaper_conditions(paper):
    """Exact author-supplied boundaries, never a second model summary."""
    return {k:paper[k] for k in ('topic_id','revision','digest','original_task','as_of','finding',
        'conditions','counterevidence','remaining','disposition','dependencies') if k in paper}


def accepted_projection(original, decision, decision_receipt):
    """A lead's bounded judgment, never runtime certification or new evidence."""
    body = json.loads(original.content)
    return {
        'receipt_id': original.tool_call_id, 'status': 'success',
        'result': {
            'task_id': body['task_id'], 'result_digest': body['result_digest'],
            'context_state': 'accepted_result_summary',
            'acceptance': decision,
            **({'workpaper_conditions':workpaper_conditions(body['workpaper'])} if body.get('workpaper') else {}),
            'acceptance_readback': {'tool': 'read_saved_result', 'arguments': {'tool_call_id': decision_receipt}},
            'meaning': 'Lead accepted this bounded result, not the entire report. Reopen if material evidence changes.',
        },
        'original_readback': {'tool': 'read_saved_result', 'arguments': {'tool_call_id': original.tool_call_id}},
    }
