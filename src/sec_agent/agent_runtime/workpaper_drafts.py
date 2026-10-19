"""Versioned author draft operations; persistence belongs to the native graph checkpoint.

Saving is not submission, source approval, or a replacement of an accepted paper.
"""
from copy import deepcopy
import json

from pydantic import ValidationError

from .research_graph_contracts import canonical_sha256
from .calculation_bindings import claim_shape_feedback


def current_draft_issues(candidate):
    """Re-evaluate a resumed draft; immutable historical save receipts stay intact."""
    from .specialist_graph import SubmitWorkpaperAction
    try:
        SubmitWorkpaperAction.model_validate_json(json.dumps(candidate))
    except ValidationError as exc:
        return claim_shape_feedback(exc.errors(include_input=False, include_context=False,
                                               include_url=False), candidate)
    return []


def owner(state):
    return {'agent_id': state['agent_id'], 'task_id': state['task']['task_id']}


def current_draft(state):
    draft = state.get('workpaper_draft')
    if draft:
        if draft['owner'] != owner(state):
            raise ValueError('workpaper_draft_owner_mismatch')
        if canonical_sha256(draft['arguments']) != draft['digest']:
            raise ValueError('workpaper_draft_digest_mismatch')
        return draft
    original = (state.get('last_submission_attempt') or {}).get('arguments')
    if not isinstance(original, dict):
        raise ValueError('workpaper_draft_candidate_missing')
    return {'owner': owner(state), 'arguments': deepcopy(original),
            'digest': canonical_sha256(original), 'baseline_digest': canonical_sha256(original),
            'receipts': {}, 'saved_batches': 0, 'changed_paths': []}


def save_draft(state, action):
    from .specialist_graph import (apply_workpaper_edits, resolve_workpaper_revision,
                                   SubmitWorkpaperAction, workpaper_edit_path)
    draft = current_draft(state)
    # Context binding can change on replay. Operation content and expected version cannot.
    identity = action.model_dump(mode='json', exclude={'context_digest', 'reason_summary'})
    digest = canonical_sha256(identity)
    prior = draft['receipts'].get(action.operation_id)
    if prior:
        if prior['request_digest'] != digest:
            raise ValueError('workpaper_draft_operation_id_conflict')
        return deepcopy(draft), {**prior['receipt'], 'replayed': True,
                                  'current_draft_digest': draft['digest']}
    resolved = resolve_workpaper_revision(action, state.get('pending_workpaper_revision'), current_base=draft['digest'])
    from .draft_rebase import assess_draft_rebase, field_fingerprints
    rebase = None
    if resolved.base_submission_digest != draft['digest']:
        rebase = assess_draft_rebase(draft, resolved)
        if rebase['conflicts']:
            from .specialist_graph import WorkpaperEditError
            raise WorkpaperEditError('workpaper_edit_base_conflict', [
                {**issue, 'requested_base': rebase['requested_base'], 'current_base': rebase['current_base'],
                 'safe_edit_indexes': rebase['safe_edit_indexes'], 'batch_applied': False}
                for issue in rebase['conflicts']])
        resolved = resolved.model_copy(update={'base_submission_digest': draft['digest']})
    candidate = apply_workpaper_edits(draft['arguments'], resolved)
    warnings = []
    repairs = []
    try:
        SubmitWorkpaperAction.model_validate_json(json.dumps(candidate))
    except ValidationError as exc:
        issues = exc.errors(include_input=False, include_context=False, include_url=False)
        from .draft_validation import normalize_response_metadata
        candidate, repairs = normalize_response_metadata(candidate, issues)
        if repairs:
            try:
                SubmitWorkpaperAction.model_validate_json(json.dumps(candidate))
                issues = []
            except ValidationError as remaining:
                issues = remaining.errors(include_input=False, include_context=False, include_url=False)
        # Cross-field completeness can be unfinished between batches. Invalid field
        # types/identities/paths are never accepted as a draft operation.
        structural = [e for e in issues if e['type'] != 'value_error']
        if structural:
            raise ValueError('workpaper_draft_field_invalid:' + json.dumps(structural))
        warnings = claim_shape_feedback(issues, candidate)
    changed = list(dict.fromkeys(workpaper_edit_path(draft['arguments'], e) for e in resolved.edits))
    from .draft_validation import draft_change_status
    baseline = ((state.get('task_context') or {}).get('accepted_revision_baseline') or {}).get('submission')
    baseline = baseline or state['last_submission_attempt']['arguments']
    change_status = draft_change_status(baseline, candidate)
    receipt = {'saved': True, 'submitted': False, 'accepted': False,
               'replayed': False, 'previous_draft_digest': draft['digest'],
               'operation_id': action.operation_id, 'draft_digest': canonical_sha256(candidate),
               'changed_paths': changed, 'draft_issues': warnings,
               'automatic_repairs': repairs, 'change_status': change_status,
               'validation_status': 'draft_only_full_validation_on_finalize'}
    if rebase is not None:
        receipt['version_reconciliation'] = rebase
    notes = [{'edit_index': i, 'path': workpaper_edit_path(draft['arguments'], edit),
              'value_note': edit.value_note}
             for i, edit in enumerate(resolved.edits)
             if 'value_note' in edit.model_fields_set]
    if notes:
        receipt['edit_notes'] = notes
    from .calculation_bindings import calculation_binding_issues
    binding_issues = calculation_binding_issues(candidate, state.get('notebook') or {}, draft['arguments'])
    if binding_issues:
        receipt['calculation_binding_issues'] = [{**issue,
            'blocks_final_submission': issue['blocking'], 'blocking': False,
            'stage': 'saved_draft_advisory'} for issue in binding_issues]
    result = {**deepcopy(draft), 'arguments': candidate, 'digest': receipt['draft_digest'],
              'saved_batches': draft['saved_batches'] + 1,
              'changed_paths': list(dict.fromkeys([*draft['changed_paths'], *changed])),
              'latest_changed_paths': changed, 'draft_issues': warnings}
    result['change_status'] = change_status
    result.setdefault('version_fingerprints', {})[draft['digest']] = field_fingerprints(draft['arguments'])
    result['receipts'][action.operation_id] = {'request_digest': digest, 'receipt': receipt}
    return result, receipt


def finalize_draft(state, action):
    from .specialist_graph import SubmitWorkpaperAction
    draft = current_draft(state)
    if action.draft_digest != draft['digest']:
        raise ValueError('workpaper_draft_stale_finalize_version')
    return SubmitWorkpaperAction.model_validate_json(json.dumps({**draft['arguments'],
        'context_digest': action.context_digest, 'reason_summary': action.reason_summary}))
