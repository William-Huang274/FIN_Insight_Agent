"""Small model views over immutable, exactly readable research receipts."""
from copy import deepcopy


def quantitative_feedback_view(check, receipt_id, *, pointer='/quantitative_change_check'):
    """Keep every finding; move repeated context/basis into the canonical receipt.

    This is not a semantic filter or a second summary. Counts explicitly disclose
    context not inlined, and JSON pointers address the unchanged saved JSON.
    """
    def readback(path):
        return {'tool': 'read_saved_result', 'arguments': {
            'tool_call_id': receipt_id, 'json_pointer': path}}
    findings = []
    for i, finding in enumerate(check.get('findings', [])):
        item = {k: deepcopy(v) for k, v in finding.items()
                if k not in {'basis', 'calculations', 'cited_claim_context'}}
        item['details_readback'] = readback(f'{pointer}/findings/{i}')
        findings.append(item)
    contexts = []
    for i, row in enumerate(check.get('cited_claim_context', [])):
        # These are candidate comparisons, not findings. Keep a complete index
        # of affected sentences without echoing fallible historical prose and
        # large source chains in every note-save acknowledgement.
        contexts.append({'sentence': row.get('sentence'),
            'earlier_statements_count': len(row.get('earlier_statements', [])),
            'evidence_receipts': list(dict.fromkeys(e.get('receipt') for e in row.get('evidence', []) if e.get('receipt')))})
        contexts[-1]['details_readback'] = readback(f'{pointer}/cited_claim_context/{i}')
    return {'status': check.get('status', 'advisory'),
        'coverage': deepcopy(check.get('coverage')), 'findings': findings,
        'cited_claim_context': contexts,
        'context_counts': {k: len(check.get(k, [])) for k in
            ('linked_ratio_bases', 'cited_claim_context')},
        'full_check_readback': readback(pointer),
        'notice': 'All findings and candidate-comparison sentences are listed. Exact bases, earlier wording and cited context remain in the saved receipt. Read relevant comparisons before synthesizing or resolving an issue; an empty findings list is not financial approval.'}
