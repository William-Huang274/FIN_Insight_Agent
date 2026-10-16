"""Explain rejected references using saved observations, never inferred evidence."""
from copy import deepcopy
import json

from .reference_repair import resolve_reference


def reference_issue(error, submission, notebook, delegated_work=None):
    prefix, _, source_id = error.partition(':')
    if prefix == 'fact_reference_authority_invalid':
        from .calculation_bindings import classification_issue
        return classification_issue(error, submission, notebook)
    if prefix == 'calculation_binding':
        from .calculation_bindings import calculation_binding_issues
        code, _, ref = source_id.partition(':')
        matches = [r for r in calculation_binding_issues(submission, notebook)
                   if r['code'] == code and r['source_id'] == ref]
        if matches:
            return {**matches[0], 'message': error}
        return None
    fields = {'unknown_evidence_id': 'evidence_ids',
              'non_evidence_reference_cited': 'evidence_ids', 'unknown_fact_id': 'fact_ids'}
    if prefix not in fields:
        return None
    field = fields[prefix]
    locations = [['claims', i, field, j] for i, claim in enumerate(submission.get('claims', []))
                 for j, value in enumerate(claim.get(field, [])) if value == source_id]
    refs = {ref['ref_id']: ref for obs in notebook.get('observations', [])
            for ref in obs.get('references', [])}
    result = {'location': locations[0] if locations else ['references'],
              'affected_locations': locations, 'type': 'reference_validation',
              'message': error, 'source_id': source_id,
              'origin': 'runtime_observed_reference_navigation',
              'diagnosis': 'unobserved_reference',
              'instruction': 'This ID is not bound in this author notebook. Read its source or restore '
                  'the original dependency observation, then use the returned ID. Do not invent an ID '
                  'or remove support while retaining the assertion. Use local revision for changed fields; '
                  'unchanged workpaper content need not be resubmitted.'}
    exact = refs.get(source_id)
    if exact and (exact.get('writer_citable') if field == 'evidence_ids'
                  else exact.get('authority_state') in {'numeric_fact', 'non_authoritative_metric'}):
        result.update(diagnosis='observed_since_rejection',
            instruction='This ID is now present in the author notebook. The saved rejection is historical; '
                'check the current candidate and resubmit local changes for full citation validation. '
                'Presence alone does not confirm quote or claim correctness.')
        return result
    fixed, spelling = resolve_reference(source_id, refs)
    if spelling and spelling['status'] == 'repaired':
        result.update(diagnosis='unique_observed_spelling_match', suggested_id=fixed,
            instruction='A unique same-namespace observed ID matches this spelling. Check the indicated '
                'reference and correct only affected bindings with local revision. This suggestion does '
                'not establish claim support or bypass citation validation.')
        return result
    if spelling and spelling['status'] == 'ambiguous':
        result.update(diagnosis='ambiguous_reference_spelling', candidates=spelling['candidates'],
            instruction='Multiple observed IDs match; do not guess. Inspect their sources and choose the '
                'one that supports this claim, then revise only affected bindings.')
        return result
    # Removing PASSAGE:: is diagnostic only, NEVER a namespace repair.
    candidate_id = source_id.removeprefix('PASSAGE::')
    ref = refs.get(candidate_id) or refs.get(source_id)
    if ref and ref.get('authority_state') == 'retrieval_candidate' and not ref.get('writer_citable'):
        readbacks = []
        for obs in notebook.get('observations', []):
            for item in obs.get('content', []):
                if (item.get('node_id') != candidate_id
                        or item.get('result_state') != 'retrieval_candidate'):
                    continue
                readback = item.get('readback')
                if isinstance(readback, dict) and readback not in readbacks:
                    readbacks.append(deepcopy(readback))
        result.update(diagnosis='candidate_not_source_bound', observed_id=ref['ref_id'],
            observed_authority=ref['authority_state'], readback_options=readbacks,
            instruction='Only a retrieval candidate is recorded, not a citable original passage. '
                'Adding PASSAGE:: does not bind evidence. Use RequestSourceAction.selection with an '
                'exact saved readback option, including document_id when supplied. If it still returns '
                'a candidate or an error, treat that as an unresolved read/binding problem, not undisclosed '
                'information. After a source-bound passage is returned, use its actual ID and exact quote '
                'in local edits to affected claims and source bindings; do not reserialize unchanged prose.')
        return result
    # Only native saved helper observations can prove another author owns it.
    # Mentioning a source in a prose workpaper is not sufficient.
    for task_id, saved in (delegated_work or {}).items():
        child = saved.get('result', {})
        if child.get('phase') != 'specialist_submission_accepted':
            continue
        for obs in child.get('notebook', {}).get('observations', []):
            if any(r.get('ref_id') == source_id and r.get('writer_citable')
                   for r in obs.get('references', [])) and obs.get('observation_digest'):
                result.update(diagnosis='helper_source_not_bound', readback={
                    'tool': 'ReadDelegatedWorkAction', 'subtask_id': task_id,
                    'section': 'source', 'source_observation_ref': obs['observation_digest']},
                    instruction='This original source exists in a saved helper result, but is not bound '
                        'in this author notebook. Restore the indicated source observation, then revise '
                        'affected bindings. Do not regenerate the helper or copy its conclusions as evidence.')
                return result
    return result


def refresh_reference_feedback(last, notebook, delegated_work=None):
    """Refresh only navigation for the rejected version; keep old receipts on disk."""
    result = deepcopy(last)
    submission = result.get('arguments') or {}
    if result.get('accepted') is not False or submission.get('action') != 'submit_workpaper':
        return result
    result['validation_issues'] = [reference_issue(issue.get('message', ''), submission,
        notebook, delegated_work) or issue for issue in result.get('validation_issues', [])]
    return result


def refresh_terminal_receipts(receipts, last):
    """Project enhanced diagnostics only onto the matching rejection, not old errors."""
    projected = deepcopy(receipts)
    old_issues = last.get('validation_issues', [])
    for receipt in projected:
        if receipt.get('name') not in {'SubmitWorkpaperAction', 'ReviseWorkpaperAction', 'FinalizeWorkpaperRevisionAction'}:
            continue
        try:
            payload = json.loads(receipt.get('content', ''))
        except (TypeError, ValueError):
            continue
        if (payload.get('accepted') is False and payload.get('validation_issues')
                and [i.get('message') for i in payload['validation_issues']]
                == [i.get('message') for i in old_issues]):
            payload['validation_issues'] = old_issues
            receipt['content'] = json.dumps(payload, ensure_ascii=False)
    return projected
