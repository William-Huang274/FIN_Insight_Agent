from hashlib import sha256
import pytest
from scripts.engineering.retrieval_evidence_spans import cover_reviewed_span, retrieved_span_covered


def bundle(windows):
    text = 'previous table\nCash 100 million at December 31, 2025\nrestriction applies'
    return {'source': {'id': 'source'}, 'text': text, 'chunks': [
        {'id': name, 'source_char_start': lo, 'source_char_end': hi,
         'body': text[lo:hi], 'digest': sha256(text[lo:hi].encode()).hexdigest()}
        for name, lo, hi in windows]}


def test_overlap_does_not_become_extra_mandatory_evidence():
    b = bundle([('previous', 0, 20), ('answer', 10, 60)])
    result = cover_reviewed_span(b, 14, 51)
    assert [c['chunk_id'] for c in result] == ['answer']
    assert result[0]['quote'] == b['text'][14:51]


def test_required_unit_and_amount_across_boundary_are_both_retained():
    b = bundle([('left', 0, 25), ('right', 22, 60)])
    assert [c['chunk_id'] for c in cover_reviewed_span(b, 14, 51)] == ['left', 'right']
    b['chunks'][1]['source_char_start'] = 26
    b['chunks'][1]['body'] = b['text'][26:60]
    b['chunks'][1]['digest'] = sha256(b['chunks'][1]['body'].encode()).hexdigest()
    with pytest.raises(ValueError, match='uncovered_gap'):
        cover_reviewed_span(b, 14, 51)


def test_corrupt_original_is_not_accepted_as_an_alternative():
    b = bundle([('answer', 10, 60)])
    b['chunks'][0]['body'] = 'Cash 999 billion'
    with pytest.raises(ValueError, match='identity_mismatch'):
        cover_reviewed_span(b, 14, 51)


def test_retrieved_alternative_cover_counts_without_relaxing_original_span():
    b = bundle([('single', 10, 60), ('left', 0, 30), ('right', 25, 60)])
    assert retrieved_span_covered(b, 14, 51, ['single'])
    assert retrieved_span_covered(b, 14, 51, ['left', 'right'])
    assert not retrieved_span_covered(b, 14, 51, ['left'])
    with pytest.raises(ValueError, match='unknown_chunk_identity'):
        retrieved_span_covered(b, 14, 51, ['another-source-id'])
