"""A revision execution window over host state, not another plan or validator.

Only explicit finding IDs, claim IDs, paths and exact quoted spans locate work.
The full paper and budget remain in the canonical context and its readback.
"""
from copy import deepcopy

import jsonpointer


def revision_document_receipt(receipt, role):
    """Read manuscript content without reissuing its old task checklist.

    The canonical field stays exact at view=record. This projection is used by
    both live reads and restored reads, before pagination, not by the validator.
    """
    result = deepcopy(receipt)
    value = result.get('result')
    if not isinstance(value, dict):
        return result
    note = value if role['path'].endswith('/task_note') else value.get('task_note')
    if not isinstance(note, dict):
        return result
    active = set(role['finding_ids'])
    kept = {k: deepcopy(v) for k, v in note.items() if k == 'summary'}
    if 'finding_responses' in note:
        kept['finding_responses'] = [deepcopy(r) for r in note['finding_responses']
                                    if r.get('finding_id') in active]
    if role['changes_saved_in_this_revision'] and 'changes' in note:
        kept['changes'] = deepcopy(note['changes'])
    if role['path'].endswith('/task_note'):
        result['result'] = kept
    else:
        value['task_note'] = kept
    result['task_record_read'] = {
        'tool': 'ReadResearchHistoryAction', 'arguments': {'section': 'operation',
            'tool_call_id': 'runtime:context:/submission_to_repair/candidate/task_note', 'view': 'record'},
        'role': 'saved_research_record_not_current_revision_requirements',
        'fields': list(note),
    }
    result['revision_requirements_at'] = '/current_context/task_context/revision_task'
    result['content_projection'] = 'manuscript_and_current_revision_responses'
    return result


def project_revision_execution(context, readback, baseline, manuscript_reads=()):
    c = context
    task = c['task_context']
    repair = c['submission_to_repair']
    # Superseded duplicate guidance may still exist in a restored journal.
    # The host's revision_instruction and submission_contract own this scope.
    repair.pop('revision_guidance', None)
    candidate = repair.pop('candidate')
    root = '/submission_to_repair/candidate'
    budget = c.pop('execution_budget', {})
    remaining = budget.get('remaining_model_turns')
    c['execution_window'] = {
        'current_request_authorized': remaining > 0 if isinstance(remaining, int) else None,
        'enforcement': 'host_hard_limits_unchanged',
        'subsequent_requests_guaranteed': False,
        'on_limit': 'persist_unfinished_draft_without_submission',
        'budget_readback': readback('/execution_budget'),
    }
    # Retire the ordinary research note/checkpoint instruction in this stage.
    # The tool remains available for voluntary research notes and source focus.
    task.pop('working_state_guidance', None)
    task['revision_progress'] = {
        'storage': 'native_draft_checkpoint',
        'saved_batches': (repair.get('draft_state') or {}).get('saved_batches', 0),
        'draft_digest': repair.get('base_submission_digest'),
        'latest_changed_paths': (repair.get('draft_state') or {}).get('latest_changed_paths', []),
        'separate_note_required': False,
        'submitted': False,
        'observed_changes': (repair.get('draft_state') or {}).get('change_status'),
    }
    findings = task.get('revision_feedback') or []
    responses = (candidate.get('task_note') or {}).get('finding_responses') or []
    prior = {r.get('finding_id'): r for r in
             ((baseline.get('task_note') or {}).get('finding_responses') or []) if isinstance(r, dict)}
    changed_paths = (repair.get('draft_state') or {}).get('changed_paths') or []
    responses_saved = any(p == '/task_note' or p.startswith('/task_note/finding_responses')
                          for p in changed_paths)
    responded = {r.get('finding_id') for r in responses if isinstance(r, dict)
                 and responses_saved and r != prior.get(r.get('finding_id'))}
    pending = [f for f in findings if isinstance(f, dict) and f.get('finding_id') not in responded]
    # Response presence means only author-reported disposition, not correctness.
    selected = pending[0] if pending else None
    validation = repair.get('validation_feedback') or {}
    feedback = repair.get('last_edit_feedback') or {}
    local_error = repair.get('pending_edit_validation') or (
        feedback if feedback.get('saved') is False or feedback.get('batch_applied') is False else None)
    current_errors = validation.get('issues') if validation.get('binding') == 'current_candidate' else []
    mode = ('repair_current_error' if local_error or current_errors else
            'edit_finding_fragment' if selected else 'reconcile_saved_draft')
    step = {
        'kind': mode,
        'finding_id': selected.get('finding_id') if selected else None,
        'pending_finding_ids': [f.get('finding_id') for f in pending],
        'author_responded_finding_ids': sorted(x for x in responded if isinstance(x, str)),
        'completion': 'saved_change_or_needed_read_result_not_whole_revision',
        'scope': 'focus_not_edit_allowlist',
        'related_changes': 'author_assessed_before_explicit_final_submission',
    }
    repair['candidate_readback'] = readback(root)
    repair['candidate_fields'] = list(candidate)
    repair['claim_ids'] = [r['claim_id'] for r in candidate.get('claims', []) if 'claim_id' in r]
    repair['field_reads'] = {k: readback(root + '/' + k.replace('~', '~0').replace('/', '~1'))
                             for k in candidate}
    claim_ids = set((selected or {}).get('claim_ids') or [])
    fragment = {'claims': [deepcopy(r) for r in candidate.get('claims', []) if r.get('claim_id') in claim_ids],
                'unresolved_target_claim_ids': sorted(claim_ids - set(repair['claim_ids']))}
    quote = (selected or {}).get('problematic_quote')
    prose = candidate.get('narrative_markdown')
    if isinstance(quote, str) and quote and isinstance(prose, str):
        offsets = []
        start = 0
        while (start := prose.find(quote, start)) >= 0:
            offsets.append(start)
            start += len(quote)
        fragment['exact_prose_matches'] = [{'path': '/narrative_markdown', 'offset': i,
                                            'text': quote} for i in offsets]
    repair['current_fragment'] = fragment
    from .revision_manuscript import editing_surface
    repair['manuscript'] = editing_surface(candidate, fragment, manuscript_reads, readback)
    repair['latest_saved_fields'] = {}
    for path in (repair.get('draft_state') or {}).get('latest_changed_paths') or []:
        try:
            repair['latest_saved_fields'][path] = deepcopy(jsonpointer.resolve_pointer(candidate, path))
        except jsonpointer.JsonPointerException:
            pass
    task['revision_step'] = step
    task['revision_task']['candidate_at'] = '/current_context/submission_to_repair/candidate_readback'
    return c
