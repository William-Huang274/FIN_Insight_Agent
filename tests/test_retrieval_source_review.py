from copy import deepcopy
from hashlib import sha256
import json

import pytest

from scripts.engineering.retrieval_source_review import validate_source_review


def example():
    body = 'Heading\nCash 10 million.'
    digest = sha256(body.encode()).hexdigest()
    raw = json.dumps({'source': {'document_id': 'd'}, 'nodes': [{
        'node_id': 'n', 'content': body, 'content_sha256': digest,
        'original_source': {'source_id': 's', 'source_digest': 'original-digest',
                            'original_node_id': 'original-n', 'source_char_start': 100}
    }]}).encode()
    proof = {'node_id': 'n', 'body_sha256': digest, 'source_id': 's',
             'source_digest': 'original-digest', 'original_node_id': 'original-n',
             'source_char_start': 108, 'source_char_end': 124, 'quote': 'Cash 10 million.'}
    questions = [{'id': lang, 'query': query, 'family': 'cash', 'language': lang,
                  'source_document_id': 'd', 'source_review_file_sha256': sha256(raw).hexdigest(),
                  'answerability': 'answerable', 'required_evidence': [deepcopy(proof)]}
                 for lang, query in [('en', 'Cash?'), ('zh', '现金？')]]
    return questions, {'d': raw}


def test_exact_source_first_proofs_do_not_claim_quality():
    q, sources = example()
    result = validate_source_review(q, sources)
    assert result['verified_proof_occurrences'] == 2
    assert result['financial_correctness_automatically_verified'] is False
    assert result['retrieval_executed'] is False


def test_empty_review_cannot_pass():
    with pytest.raises(ValueError, match='questions_required'):
        validate_source_review([], {})


@pytest.mark.parametrize('field,value,error', [
    ('source_char_start', 107, 'quote_coordinate'),
    ('source_char_end', 999, 'outside_original'),
    ('source_char_start', True, 'coordinates_required'),
    ('quote', 'Cash 100 million.', 'quote_coordinate'),
    ('source_digest', 'other', 'original_identity'),
    ('original_node_id', 'other', 'original_node'),
    ('node_id', 'other-source-node', 'outside_reviewed'),
    ('body_sha256', 'other', 'body_digest'),
])
def test_rejects_unbound_evidence(field, value, error):
    q, sources = example()
    q[0]['required_evidence'][0][field] = value
    with pytest.raises(ValueError, match=error):
        validate_source_review(q, sources)


def test_snapshot_byte_change_requires_review_again():
    q, sources = example()
    sources['d'] += b'\n'
    with pytest.raises(ValueError, match='file_changed'):
        validate_source_review(q, sources)


def test_counterevidence_is_not_no_answer():
    q, sources = example()
    q[0]['answerability'] = 'unanswerable'
    with pytest.raises(ValueError, match='absence_requires'):
        validate_source_review(q, sources)


def test_bilingual_labels_cannot_silently_change_scope():
    q, sources = example()
    q[0]['answerability'] = 'answerable_with_counterevidence'
    with pytest.raises(ValueError, match='bilingual_evidence'):
        validate_source_review(q, sources)
