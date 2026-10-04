"""Version-bound inspection records; persistence never supplies a verdict."""
from copy import deepcopy
from langchain_core.messages import AIMessage, ToolMessage
from .research_graph_contracts import canonical_sha256


def check_key(check):
    return canonical_sha256([check['paper_id'], check['paper_digest'], check['dimension'],
        check['field_path'], check.get('semantic_target_id')])


def merge_checks(previous, checks):
    result = deepcopy(previous)
    for check in checks:
        row = check.model_dump(mode='json') if hasattr(check, 'model_dump') else deepcopy(check)
        result[check_key(row)] = row
    return result


def restore_checks(saved):
    """Migrate only successful legacy submissions; failed drafts are not checks."""
    from langchain_core.messages import messages_from_dict
    pending, records = {}, {}
    for message in messages_from_dict(saved.get('messages', [])):
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                if call['name'] == 'submit_case_review':
                    args = call.get('args', {})
                    if isinstance(args, dict) and isinstance(args.get('review'), dict):
                        pending[call['id']] = args['review'].get('inspection_checks', [])
        elif isinstance(message, ToolMessage) and message.tool_call_id in pending:
            checks = pending.pop(message.tool_call_id)
            if message.status == 'success' and 'Review handoff accepted' in str(message.content):
                records = merge_checks(records, checks)
    return {**records, **deepcopy(saved.get('recorded_inspections', {}))}


def restore_findings(saved, latest_review):
    """Retain findings from successful legacy review submissions, including withdrawals."""
    from langchain_core.messages import messages_from_dict
    records = deepcopy(saved.get('recorded_findings', {}))
    pending = {}
    for message in messages_from_dict(saved.get('messages', [])):
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                args=call.get('args', {})
                if call['name']=='submit_case_review' and isinstance(args,dict) and isinstance(args.get('review'),dict):
                    pending[call['id']]=args['review']
        elif isinstance(message, ToolMessage) and message.tool_call_id in pending:
            review=pending.pop(message.tool_call_id)
            if message.status=='success' and 'Review handoff accepted' in str(message.content):
                records.update({f['finding_id']:deepcopy(f) for f in review.get('findings',[])})
                for key in review.get('withdrawn_finding_reasons',{}):records.pop(key,None)
    records.update({f['finding_id']:deepcopy(f) for f in latest_review.get('findings',[])})
    for key in latest_review.get('withdrawn_finding_reasons',{}):records.pop(key,None)
    return records


def inspection_progress(records, artifacts):
    from .review_inspection import inspection_manifest
    result = {}
    for pid, scope in inspection_manifest(artifacts).items():
        checks = [c for c in records.values() if c['paper_id'] == pid and c['paper_digest'] == scope['paper_digest']]
        done = [c for c in checks if c['status'] != 'unresolved']
        claims = {i for c in done if c['dimension'] == 'claim_support' for i in c.get('claim_ids', [])}
        targets = {c.get('semantic_target_id') for c in done if c['dimension'] == 'prose_consistency'}
        result[pid] = {'saved_checks':len(checks),
            'missing_dimensions': sorted(set(scope['required_dimensions']) - {c['dimension'] for c in done}),
            'missing_claim_ids': sorted(set(scope['material_claim_ids']) - claims),
            'missing_semantic_target_ids': [t['target_id'] for t in scope['semantic_targets'] if t['target_id'] not in targets]}
    return result
