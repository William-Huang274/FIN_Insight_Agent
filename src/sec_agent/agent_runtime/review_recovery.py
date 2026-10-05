"""Public incomplete-review handoff to the existing Lead, without private messages."""
from copy import deepcopy
from .case_review_agent import case_review_scope_digest


def public_confirmation(record):
    """Project review handoff; recovery journals belong only to their author.

    Keep the native record intact for resumption. A submitted but incomplete
    review remains incomplete in this view; projection is not acceptance.
    """
    if not record:
        return {}
    review = record.get('review', {})
    public = {key: deepcopy(review[key]) for key in (
        'run_id', 'run_invocation_id', 'phase', 'scope_digest',
        'material_finding_count', 'pending_saved_material_finding_count') if key in review}
    for role in ('counter', 'verifier'):
        if role not in review:
            continue
        row = review[role]
        public[role] = {key: deepcopy(row[key]) for key in (
            'status', 'review', 'recorded_findings', 'model_calls', 'tool_calls') if key in row}
        public[role]['tool_feedback'] = deepcopy(row.get('tool_feedback', [])[-4:])
        public[role]['resumable'] = bool(row.get('recovery_state'))
    return {**{key: deepcopy(record[key]) for key in ('context', 'correction_round') if key in record},
            'review': public}


def review_recovery_handoff(review, artifacts, question):
    from .workpaper_changes import paper_versions
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
            # Triage must expose one consistent namespace for advisory and
            # material findings alike; it cannot execute any author repair.
            item = deepcopy(f)
            item.update(finding_id=role + ':' + f['finding_id'], reviewer=role, original_finding_id=f['finding_id'])
            feedback.setdefault(f['paper_id'], []).append(item)
        records[role] = {'status': row.get('status'), 'summary': submitted.get('summary'),
            'findings': [deepcopy(item) for items in feedback.values() for item in items if item['reviewer']==role],
            'inspection_checks': submitted.get('inspection_checks', []),
            'unresolved_data_requests': submitted.get('unresolved_data_requests', []),
            'research_limitations': submitted.get('research_limitations', []),
            'model_calls': row.get('model_calls'), 'tool_calls': row.get('tool_calls'),
            'tool_feedback': deepcopy(row.get('tool_feedback', [])[-4:]),
            'resumable': bool(row.get('recovery_state')),
            'execution_notice': 'Formal review not submitted; saved findings are partial, not acceptance.' if not submitted else None}
    return {'scope_digest': review['scope_digest'], 'incomplete_reviewers': roles,
        'feedback': feedback, 'review_records': records,
        'required_dispositions': [{'paper_id':pid,'finding_id':f['finding_id'],'severity':f['severity']} for pid,items in feedback.items() for f in items],
        'candidate_changed':False,
        'available_candidate_versions':paper_versions(artifacts),
        'available_prerequisite':'current_candidate',
        'notice': 'Current public artifacts and tool failures only. Saved reviewer private histories stay with their original owners. '
                  'No author edits have occurred: the current candidate is unchanged. Proposed repairs are pending, never performed. '
                  'Do not assign checking a newly added paragraph that does not exist. Copy the exact namespaced IDs from required_dispositions. '
                  'Do not call incomplete work clean. Choose one bounded continuation of missing review checks or stop; no synthesis or author edits here.'}
