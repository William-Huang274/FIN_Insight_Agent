"""Explicit, host-pinned migration of old financial receipts, not ACP history."""
import base64
from hashlib import sha256
import json
from pathlib import Path

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


def imported_web_navigation(imported):
    """Receipt-specific authority derived only after legacy_receipts verifies bytes.

    Original messages/locators remain unchanged. The web reader can rebind these
    exact public directories to the admitted execution, with its own date scope.
    This does not authorize other receipts from the same historical task.
    """
    from sec_agent.research_foundation.external_sources import DiscoveryReceipt
    result = {}
    for message in imported.get('messages', []):
        artifact = getattr(message, 'artifact', None) or {}
        if (getattr(message, 'name', None) != 'read_public_source' or
                (getattr(message, 'status', None) != 'success' and not artifact.get('execution_stop'))):
            continue
        for raw in artifact.get('web_navigation_receipts', []):
            if raw.get('receipt_digest') in result:
                continue
            receipt = DiscoveryReceipt.model_validate(raw)
            result[receipt.receipt_digest] = receipt.case_id
    return result


def legacy_receipts(binding, *, grant):
    """Only deployment-owned exports may cross a replaced graph boundary.

    An old nested graph may no longer be resolvable through the new graph's SDK
    state endpoint. Operators export that exact checkpoint, retain its original
    coordinates and pin the bytes. Browser/model arguments cannot select it.
    This function never restores summary/instruction state into native history.
    """
    if binding['execution_id'] != grant['execution_id'] or binding['manifest_digest'] != grant['manifest_digest']:
        raise ValueError('harness_legacy_import_authority_mismatch')
    checkpoint = binding['source_checkpoint']
    # LangGraph uses an empty string for the root graph namespace.
    if not checkpoint.get('checkpoint_id') or not isinstance(checkpoint.get('checkpoint_ns'), str):
        raise ValueError('harness_legacy_import_checkpoint_required')
    raw = Path(binding['path']).read_bytes()
    if sha256(raw).hexdigest() != binding['sha256']:
        raise ValueError('harness_legacy_import_digest_mismatch')
    envelope = json.loads(raw)
    state = JsonPlusSerializer().loads_typed((envelope['type'], base64.b64decode(envelope['blob'], validate=True)))
    if state.get('question') != grant['question']:
        raise ValueError('harness_legacy_import_question_mismatch')
    messages = state.get('messages', [])
    if any(not getattr(m, 'id', None) for m in messages):
        raise ValueError('harness_legacy_import_stable_message_id_required')
    imported = {'messages': messages, 'harness_import_digest': binding['sha256']}
    if binding.get('report_checkpoint'):
        from .research_graph_contracts import canonical_sha256
        expected = binding['report_checkpoint']
        report, revision = state.get('report'), state.get('report_version')
        if (not report or type(revision) is not int or revision < 1
                or expected != {'version': revision, 'digest':canonical_sha256(report)}):
            raise ValueError('harness_import_report_checkpoint_mismatch')
        imported.update(report=report, report_version=revision)
    if binding.get('review_checkpoint'):
        review=state.get('active_report_review') or {}
        expected=binding['review_checkpoint']
        actual={'reviewed_report_digest':review.get('reviewed_report_digest'),
                'reviewer':review.get('reviewer'),
                'opinion_sha256':sha256(review.get('opinion','').encode()).hexdigest()}
        if (not imported.get('report') or expected!=actual or not review.get('opinion')
                or actual['reviewed_report_digest']!=binding['report_checkpoint']['digest']):
            raise ValueError('harness_import_review_checkpoint_mismatch')
        imported['active_report_review']=review
    return imported
