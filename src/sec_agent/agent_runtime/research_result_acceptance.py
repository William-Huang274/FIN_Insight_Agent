"""Version-bound lead decisions; saved tool receipts remain the source of truth."""
import json

from langchain_core.messages import ToolMessage
from .research_graph_contracts import canonical_sha256


def result_version(record):
    return canonical_sha256({k: record.get(k) for k in ('request', 'opinion', 'assessment')})


def latest_decisions(messages):
    decisions = {}
    for m in messages:
        if isinstance(m, ToolMessage) and m.name == 'assess_research_result' and m.status == 'success':
            body = json.loads(m.content)
            if body.get('decision_recorded'):
                decisions[body['task_id']] = (body, m.tool_call_id)
    return decisions


def accepted_projection(original, decision, decision_receipt):
    """A lead's bounded judgment, never runtime certification or new evidence."""
    body = json.loads(original.content)
    return {
        'receipt_id': original.tool_call_id, 'status': 'success',
        'result': {
            'task_id': body['task_id'], 'result_digest': body['result_digest'],
            'context_state': 'accepted_result_summary',
            'acceptance': decision,
            'acceptance_readback': {'tool': 'read_saved_result', 'arguments': {'tool_call_id': decision_receipt}},
            'meaning': 'Lead accepted this bounded result, not the entire report. Reopen if material evidence changes.',
        },
        'original_readback': {'tool': 'read_saved_result', 'arguments': {'tool_call_id': original.tool_call_id}},
    }
