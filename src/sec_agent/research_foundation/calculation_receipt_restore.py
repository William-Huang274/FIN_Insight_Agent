"""Replay calculator receipts without replacing their original capture identity."""
from copy import deepcopy

from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256


def preserve_verified_capture_identity(fresh, saved):
    """Allow a later capture of identical public text, not different evidence.

    Passage identity binds URL/document, offset and content. Capture timestamps
    and capture receipt digests may differ after a second fetch. All other
    provenance must match; the saved calculation retains its original capture.
    The caller still compares the entire recalculated receipt with the saved one.
    """
    fresh = deepcopy(fresh)
    for name, operand in fresh['operands'].items():
        old = saved['operands'].get(name, {})
        current = operand.get('source_provenance', {})
        previous = old.get('source_provenance', {})
        if (current == previous or
                current.get('source_role') != 'external_public_source_unverified' or
                previous.get('source_role') != 'external_public_source_unverified'):
            continue
        left, right = deepcopy(current), deepcopy(previous)
        for value in (left, right):
            locator = value.get('source_locator', {})
            for field in ('captured_at', 'capture_receipt_digest'):
                if not isinstance(locator.get(field), str) or not locator[field]:
                    raise ValueError('organization_restore_capture_identity_missing')
                locator.pop(field)
        if left == right:
            operand['source_provenance'] = deepcopy(previous)
    body = {key: value for key, value in fresh.items() if key != 'calculation_id'}
    fresh['calculation_id'] = 'CALC::' + canonical_sha256(body)[:24]
    return fresh
