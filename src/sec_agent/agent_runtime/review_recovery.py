"""Public incomplete-review handoff to the existing Lead, without private messages."""
from copy import deepcopy
from .case_review_agent import case_review_scope_digest


def review_recovery_handoff(review, artifacts, question):
    if review.get('phase') != 'case_review_incomplete' or review.get('scope_digest') != case_review_scope_digest(artifacts, question):
        raise ValueError('review_triage_requires_current_incomplete_scope')
    roles, feedback, records = [], {}, {}
    for role in ('counter', 'verifier'):
        row = review[role]
        submitted = row.get('review') or {}
        findings = {**row.get('recorded_findings', {}), **{f['finding_id']: f for f in submitted.get('findings', [])}}
        if row.get('status') != 'review_submitted':
            roles.append(role)
        for f in findings.values():
            if f['severity'] == 'material':
                item = deepcopy(f)
                item.update(finding_id=role + ':' + f['finding_id'], reviewer=role, original_finding_id=f['finding_id'])
                feedback.setdefault(f['paper_id'], []).append(item)
        records[role] = {'status': row.get('status'), 'summary': submitted.get('summary'),
            'findings': list(findings.values()), 'inspection_checks': submitted.get('inspection_checks', []),
            'unresolved_data_requests': submitted.get('unresolved_data_requests', []),
            'model_calls': row.get('model_calls'), 'tool_calls': row.get('tool_calls'),
            'tool_feedback': deepcopy(row.get('tool_feedback', [])[-4:]),
            'resumable': bool(row.get('recovery_state')),
            'execution_notice': 'Formal review not submitted; saved findings are partial, not acceptance.' if not submitted else None}
    return {'scope_digest': review['scope_digest'], 'incomplete_reviewers': roles,
        'feedback': feedback, 'review_records': records,
        'notice': 'Current public artifacts and tool failures only. Saved reviewer private histories stay with their original owners. '
                  'Do not call incomplete work clean. Choose one bounded continuation of missing review checks or stop; no synthesis or author edits here.'}
