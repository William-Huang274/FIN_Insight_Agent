"""Repair identifier spelling against this task's observed records, not prose.

Never fabricate evidence or change namespaces. Unresolved IDs remain visible
author errors; accepting a working note does not validate a final citation.
"""
from copy import deepcopy


def _one_edit(a, b):
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long = sorted((a, b), key=len)
    i = next((i for i, (x, y) in enumerate(zip(short, long)) if x != y), len(short))
    return short[i:] == long[i + 1:]


def resolve_reference(value, observed):
    if value in observed:
        return value, None
    namespace, sep, suffix = value.rpartition('::')
    # Short human labels are too easy to confuse. Prefix completion needs at
    # least 16 identifier characters; one-edit repair requires a long ID too.
    candidates = sorted(x for x in observed if sep and len(suffix) >= 16
        and x.rpartition('::')[0] == namespace
        and (x.startswith(value) or _one_edit(suffix, x.rpartition('::')[2])))
    if len(candidates) == 1:
        return candidates[0], {'submitted_id': value, 'resolved_id': candidates[0],
            'status': 'repaired', 'basis': 'unique_observed_same_namespace_identifier'}
    return value, {'submitted_id': value, 'status': 'ambiguous' if candidates else 'unresolved',
        'candidates': candidates, 'notice': 'Not verified evidence. Correct this reference or read its source; other research may continue.'}


def repair_working_references(note, observed):
    result = deepcopy(note)
    repairs, issues = [], []
    fields = [(result, 'retain_source_ids', '/retain_source_ids')]
    for key in ('findings', 'resolved_questions', 'subtasks'):
        fields.extend((row, 'source_ids', f'/{key}/{i}/source_ids') for i, row in enumerate(result.get(key, [])))
    for row, key, path in fields:
        for i, value in enumerate(row.get(key, [])):
            fixed, receipt = resolve_reference(value, observed)
            row[key][i] = fixed
            if receipt:
                (repairs if receipt['status'] == 'repaired' else issues).append({**receipt, 'path': f'{path}/{i}'})
    result['reference_issues'] = issues
    return result, repairs, issues
