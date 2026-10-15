"""Shared author revision scope; guidance does not decide financial correctness."""

AUTHOR_REVISION_GUIDANCE = (
    "Continue the original task from the current candidate with precise edits. "
    "Evaluate each finding against the actual affected text; reviewer and Lead requests are proposals, not source evidence. "
    "Preserve means retain correct content already in this candidate, not insert figures mentioned only in feedback. "
    "For an identifier-only defect, restore the exact source link while retaining the existing assertion and its status; "
    "repairing navigation does not require promoting an open gap into a claim or adding analysis. "
    "Use supplied source identities and saved reads; read originals when identity, factual support or a changed inference "
    "still needs checking. If that read is necessary, make the read before drafting changes that depend on its result. "
    "When evidence changes a claim, update its affected prose and bindings together. Reuse unaffected work. "
    "Answer every exact finding_id once in task_note.finding_responses, including disagreement or unresolved work. "
    "A repaired link does not establish financial correctness or completion of an unread source check."
)


def lead_repair_feedback(finding, decision):
    """Keep the reviewer defect separate from Lead's proposed remedy."""
    from copy import deepcopy
    return {**deepcopy(finding), 'lead_requested_change': decision['requested_change'],
            'lead_rationale': decision['rationale'], 'expected_progress': decision['expected_progress']}


def restore_review_request(finding, original_findings):
    """Recover legacy overwritten provenance only from a matching host record."""
    from copy import deepcopy
    result = deepcopy(finding)
    if 'lead_requested_change' in result or not result.get('lead_rationale'):
        return result
    identity = ('finding_id', 'paper_id', 'reviewer', 'original_finding_id',
                'problematic_quote', 'diagnosis', 'source_checks')
    matches = [row for row in original_findings
               if all(row.get(key) == result.get(key) for key in identity)]
    if len(matches) == 1 and matches[0].get('requested_change'):
        result['lead_requested_change'] = result['requested_change']
        result['requested_change'] = matches[0]['requested_change']
    return result
