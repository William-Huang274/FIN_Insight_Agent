"""Public incomplete-review handoff to the existing Lead, without private messages."""
from copy import deepcopy
from .case_review_agent import case_review_scope_digest


def public_review(review):
    """Lead receives judgments/findings; archived paragraph forms stay local."""
    return {key: deepcopy(value) for key, value in review.items() if key != 'inspection_checks'}


def pending_confirmation_review(state, artifacts):
    """Recover the newest stopped confirmation, never the pre-repair review."""
    candidate = state.get('case_review', {})
    if candidate.get('confirmation_context'):
        record = {'review': candidate, 'context': candidate['confirmation_context']}
    elif state.get('research_stop_reason') == 'independent_confirmation_incomplete':
        record = next((row['output'] for row in reversed(state.get('convergence_history', []))
            if row.get('actor') == 'independent_workpaper_confirmation'), None)
        if not record:
            raise ValueError('pending_confirmation_record_missing')
    else:
        return None
    from .workpaper_changes import paper_versions
    if (record['review'].get('scope_digest') != case_review_scope_digest(artifacts, state['question'])
            or record['context']['paper_version_digests'] != paper_versions(artifacts)):
        raise ValueError('pending_confirmation_requires_current_versions')
    return deepcopy(record)


def review_after_author_changes(review, before, current, question, context):
    """Retain unchanged checks; an edited paper is never approved by old checks.

    Source reads, lifetime usage and the original review remain recoverable.
    Confirmation of the pending findings is required separately from coverage.
    """
    import json
    from langchain_core.messages import HumanMessage, message_to_dict
    from .review_check_store import restore_checks, restore_findings
    from .workpaper_changes import paper_versions
    if review.get('phase') != 'case_review_incomplete' or review.get('scope_digest') != case_review_scope_digest(before, question):
        raise ValueError('author_change_review_requires_original_incomplete_scope')
    old, new = paper_versions(before), paper_versions(current)
    if old.keys() != new.keys() or not context.get('findings_to_confirm'):
        raise ValueError('author_change_review_requires_same_papers_and_pending_findings')
    changed = {pid for pid in old if old[pid] != new[pid]}
    result = deepcopy(review)
    result['scope_digest'] = case_review_scope_digest(current, question)
    result['author_change_baseline_scope_digest'] = review['scope_digest']
    for role in ('counter', 'verifier'):
        row = result[role]
        saved = deepcopy(row.get('recovery_state'))
        if not saved:
            # A completed peer can retain its public checks/findings without
            # acquiring another reviewer's private history.
            if row.get('status') != 'review_submitted':
                raise ValueError('author_change_review_requires_saved_reviewer_state:' + role)
            submitted = row.get('review') or {}
            from .review_check_store import merge_checks
            # Legacy public-only reviews cannot recover lost reads. Preserve
            # the actual question without pretending that those reads exist.
            saved = {'messages': [message_to_dict(HumanMessage(content=json.dumps({'question': question}, ensure_ascii=False)))],
                     'recorded_inspections': merge_checks({}, submitted.get('inspection_checks', [])),
                     'recorded_findings': {f['finding_id']: f for f in submitted.get('findings', [])}}
        checks = restore_checks(saved)
        findings = restore_findings(saved, row.get('review') or {})
        saved['recorded_inspections'] = {k: c for k, c in checks.items()
            if c['paper_id'] not in changed and c['paper_digest'] == new.get(c['paper_id'])}
        saved['recorded_findings'] = {k: f for k, f in findings.items() if f['paper_id'] not in changed}
        saved['author_change_projection'] = True
        saved.pop('request_summary', None)
        saved.pop('request_summary_failure', None)
        saved['messages'] = [*saved.get('messages', []), message_to_dict(HumanMessage(content=
            'Authors revised the current candidate. Historical paper text and findings are NOT the current version. '
            'Read the changed papers; independently confirm pending findings and finish necessary substantive checks. '
            'Unchanged checks and original source reads remain reusable; no financial finding is automatically closed. '
            + json.dumps({'changed_papers': sorted(changed), 'current_versions': new,
                          'revision_confirmation': context}, ensure_ascii=False)))]
        row.update(status='incomplete_no_submission', review=None, recovery_state=saved,
                   recorded_findings=deepcopy(saved['recorded_findings']))
    return result


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
        if public[role].get('review'):
            public[role]['review'] = public_review(public[role]['review'])
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
                  'Do not call incomplete work clean. Choose resume_review for missing checks on this candidate, '
                  'repair to send confirmed local issues to their authors before completing independent review, or stop. '
                  'Repair does not accept the case or permit synthesis: changed papers require new checks and '
                  'unfinished checks on unchanged papers remain pending.'}
