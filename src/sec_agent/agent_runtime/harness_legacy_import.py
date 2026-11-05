"""Explicit, host-pinned migration of old financial receipts, not ACP history."""
import base64
from hashlib import sha256
import json
from pathlib import Path

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


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
    return {'messages': messages, 'harness_import_digest': binding['sha256']}
