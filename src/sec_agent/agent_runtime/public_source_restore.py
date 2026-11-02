"""Validate exact task-owned web observations without fetching them again."""
from copy import deepcopy
from hashlib import sha256
from urllib.parse import urlsplit


def validated_public_source(item):
    if item.get('result_state') != 'source_bound_passage' or item.get('source_role') != 'external_public_source_unverified' or item.get('writer_citable') is not True:
        raise ValueError('not_observed_public_source')
    locator = item['source_locator']
    text = item['passage']
    digest = sha256(text.encode('utf-8')).hexdigest()
    doc = item['document_id']
    if (not doc.startswith('WEB::') or locator.get('document_id') != doc
            or item.get('content_sha256') != digest or locator.get('content_sha256') != digest
            or locator['character_end'] - locator['character_start'] != len(text)
            or item['passage_id'] != f"PASSAGE::{doc}::{locator['character_start']}::{digest[:16]}"
            or item.get('source_url') != locator.get('source_url')
            or urlsplit(item['source_url']).scheme not in {'https', 'http'}
            or not locator.get('capture_receipt_digest') or item.get('numeric_fact_authority') is not False):
        raise ValueError('public_source_observation_identity_changed')
    return deepcopy(item)
