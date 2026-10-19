"""Deterministic draft write-set comparison; never infer an author's new claim."""
from copy import deepcopy

import jsonpointer

from .research_graph_contracts import canonical_sha256


def field_fingerprints(arguments):
    """Host-only version metadata. No prose copies or model-visible history."""
    result = {}
    def visit(value, path):
        result[path] = canonical_sha256(value)
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, path + '/' + key.replace('~', '~0').replace('/', '~1'))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + '/' + str(index))
    visit(arguments, '')
    return result


def import_ancestor_fingerprints(state, ancestor_state):
    """Offline migration from an intact same-owner saved ancestor, not model data."""
    from .workpaper_drafts import current_draft
    draft, ancestor = current_draft(state), current_draft(ancestor_state)
    known = {r['receipt']['draft_digest'] for r in draft['receipts'].values()}
    if (ancestor['owner'] != draft['owner'] or ancestor['digest'] not in known
            or any(state.get(k) != ancestor_state.get(k) for k in ('run_id', 'run_invocation_id'))):
        raise ValueError('draft_ancestor_not_in_current_save_history')
    result = deepcopy(state)
    result['workpaper_draft'].setdefault('version_fingerprints', {})[ancestor['digest']] = field_fingerprints(ancestor['arguments'])
    return result


def assess_draft_rebase(draft, action):
    """Require known ancestry and unchanged targets or explicit exact preconditions.

    A claim update remains one edit even when only some of its fields conflict.
    A safe write set is not proof that a partial batch is semantically complete.
    """
    from .specialist_graph import workpaper_edit_path
    current = draft['arguments']
    fingerprints = draft.get('version_fingerprints', {}).get(action.base_submission_digest)
    report = {'requested_base': action.base_submission_digest, 'current_base': draft['digest'],
              'known_ancestor': fingerprints is not None, 'safe_edit_indexes': [], 'conflicts': []}
    if fingerprints is None:
        report['conflicts'] = [{'location': ['base_submission_digest'], 'code': 'unknown_edit_base',
                               'remedy': 'Original proposal retained. The host cannot verify this base; read the current candidate before correcting the version.'}]
        return report
    for index, edit in enumerate(action.edits):
        raw = edit.model_dump(mode='json')
        try:
            path = workpaper_edit_path(current, edit)
            value = jsonpointer.resolve_pointer(current, path)
            if raw.get('op') == 'update_claim':
                fields = [path + '/' + k for k in raw['changes']]
                identity = path + '/claim_id'
                if fingerprints.get(identity) != canonical_sha256(value['claim_id']):
                    raise ValueError('claim_identity_changed')
            else:
                fields = [path]
            guarded = (raw.get('op') == 'str_replace' and isinstance(value, str)
                       and sum(value.startswith(raw['old_string'], i) for i in range(len(value))) == 1)
            guarded = guarded or ('old_value' in raw and value == raw['old_value'])
            changed = [] if guarded else [p for p in fields
                if fingerprints.get(p) != canonical_sha256(jsonpointer.resolve_pointer(current, p))]
            if changed:
                report['conflicts'].append({'location': ['edits', index], 'edit_index': index,
                    'code': 'intervening_target_change', 'paths': changed,
                    'remedy': 'This edit overlaps saved changes. Original edit retained; reconcile only these fields against the current candidate. Do not overwrite them by changing the base alone.'})
            else:
                report['safe_edit_indexes'].append(index)
        except (ValueError, KeyError, TypeError, jsonpointer.JsonPointerException):
            report['conflicts'].append({'location': ['edits', index], 'edit_index': index,
                'code': 'rebase_target_unresolved', 'remedy': 'Original edit retained; resolve the exact current target before saving.'})
    return report


def save_rebase_subset(state, action, indexes):
    """Host recovery of explicitly selected safe edits; retain every other edit.

    Caller must check semantic dependencies before selecting a subset. The normal
    save path stays atomic and never silently splits an author's batch.
    """
    from .workpaper_drafts import current_draft, save_draft
    draft = current_draft(state)
    proposal_digest = canonical_sha256(action.model_dump(mode='json', exclude={'context_digest', 'reason_summary'}))
    deferred = [i for i in range(len(action.edits)) if i not in indexes]
    remaining = action.model_copy(update={'edits': tuple(action.edits[i] for i in deferred)}) if deferred else None
    for row in draft['receipts'].values():
        recovered = row['receipt'].get('recovery_selection', {})
        if (recovered.get('original_proposal_digest') == proposal_digest
                and recovered.get('applied_original_indexes') == indexes):
            return deepcopy(draft), {**row['receipt'], 'replayed': True}, remaining
    assessment = assess_draft_rebase(draft, action)
    if (not indexes or indexes != sorted(set(indexes))
            or not set(indexes) <= set(assessment['safe_edit_indexes'])):
        raise ValueError('rebase_subset_not_proven_safe')
    binding = {'original_operation_id': action.operation_id,
               'original_proposal_digest': proposal_digest,
               'requested_base': action.base_submission_digest, 'applied_base': draft['digest'],
               'applied_original_indexes': indexes,
               'deferred_original_indexes': deferred}
    selected = action.model_copy(update={'base_submission_digest': draft['digest'],
        'operation_id': 'host-rebase-' + canonical_sha256(binding),
        'edits': tuple(action.edits[i] for i in indexes)})
    updated, receipt = save_draft(state, selected)
    receipt = {**receipt, 'recovery_selection': binding, 'semantic_completion_verified': False}
    updated['receipts'][selected.operation_id]['receipt'] = deepcopy(receipt)
    return updated, receipt, remaining
