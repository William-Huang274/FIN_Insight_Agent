from copy import deepcopy
from hashlib import sha256
import json

import pytest

from scripts.engineering.retrieval_source_review import freeze_source_questions
from test_retrieval_source_review import example


def fixtures():
    questions, files = example()
    document = {'document_id': 'd', 'excluded_reasons': [], 'nodes': 1,
                'source_identities': [['source_id', 's'], ['source_digest', 'original-digest']]}
    exposure = {'documents': [document]}
    selection = {'sources': [{**document, 'review_file_sha256': sha256(files['d']).hexdigest()}]}
    return questions, files, selection, exposure


def freeze(questions, files, selection, exposure):
    raw = json.dumps(exposure).encode()
    selection = {**selection, 'source_exposure_audit_sha256': sha256(raw).hexdigest()}
    return freeze_source_questions(questions, files, json.dumps(selection).encode(), raw)


def test_freeze_cannot_leak_new_private_fields_or_mutate_review():
    q, files, selection, exposure = fixtures()
    q[0]['future_answer_hint'] = 'Secret reviewed answer'
    original = deepcopy(q)
    output = freeze(q, files, selection, exposure)
    queries = json.loads(output['queries.json'])
    assert queries == {'questions': [{'id': x['id'], 'query': x['query']} for x in q]}
    assert b'Secret' not in output['queries.json']
    assert q == original
    manifest = json.loads(output['manifest.json'])
    assert manifest['query_file_sha256'] == sha256(output['queries.json']).hexdigest()
    assert manifest['review_file_sha256'] == sha256(output['source-review.private.json']).hexdigest()
    assert manifest['retrieval_executed'] is False
    assert manifest['execution_config_frozen'] is False
    assert manifest['full_corpus_equivalent_evidence_reviewed'] is False
    assert output == freeze(q, files, selection, exposure)


def test_changed_exposure_bytes_reject():
    q, files, selection, exposure = fixtures()
    selection['source_exposure_audit_sha256'] = sha256(json.dumps(exposure).encode()).hexdigest()
    with pytest.raises(ValueError, match='audit_changed'):
        freeze_source_questions(q, files, json.dumps(selection).encode(), json.dumps(exposure).encode()+b' ')


@pytest.mark.parametrize('kind', ['source_id', 'source_digest'])
def test_cross_document_original_alias_exposure_rejects(kind):
    q, files, selection, exposure = fixtures()
    shared = next(x for x in exposure['documents'][0]['source_identities'] if x[0] == kind)
    exposure['documents'].append({'document_id': 'other-parse', 'excluded_reasons': ['old-test'],
                                 'nodes': 1, 'source_identities': [shared]})
    with pytest.raises(ValueError, match='original_was_exposed'):
        freeze(q, files, selection, exposure)


@pytest.mark.parametrize('mutation,error', [
    ('excluded', 'not_eligible'), ('missing_audit', 'not_eligible'),
    ('duplicate_audit', 'duplicate_exposure'), ('duplicate_selected', 'duplicate_selected'),
    ('identities', 'identity_changed'), ('hash', 'snapshot_changed'),
    ('incomplete', 'snapshot_incomplete'), ('selected_missing', 'scope_mismatch'),
])
def test_selection_contracts(mutation, error):
    q, files, selection, exposure = fixtures()
    if mutation == 'excluded': exposure['documents'][0]['excluded_reasons'] = ['regression-source']
    if mutation == 'missing_audit': exposure['documents'] = []
    if mutation == 'duplicate_audit': exposure['documents'] *= 2
    if mutation == 'duplicate_selected': selection['sources'] *= 2
    if mutation == 'identities': selection['sources'][0]['source_identities'] = [['source_id', 'other']]
    if mutation == 'hash': selection['sources'][0]['review_file_sha256'] = '0'*64
    if mutation == 'incomplete': exposure['documents'][0]['nodes'] = 2
    if mutation == 'selected_missing': selection['sources'] = []
    with pytest.raises(ValueError, match=error):
        freeze(q, files, selection, exposure)


def test_snapshot_proofs_cannot_masquerade_as_unexposed_source():
    q, files, selection, exposure = fixtures()
    # Valid proof/file hashes alone are insufficient: the original must belong
    # to the source whose exposure history was actually reviewed.
    for row in [exposure['documents'][0], selection['sources'][0]]:
        row['source_identities'] = [['source_id', 'other'], ['source_digest', 'other-digest']]
    with pytest.raises(ValueError, match='outside_exposure_audit'):
        freeze(q, files, selection, exposure)
