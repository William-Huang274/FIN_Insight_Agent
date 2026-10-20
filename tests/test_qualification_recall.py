import pytest
from scripts.engineering.qualify_retrieval_recall import ranking_metrics, rrf


def test_missing_evidence_and_duplicates_do_not_inflate_recall():
    result = ranking_metrics(['a', 'a', 'x', 'b'], ['a', 'b', 'missing'])
    assert result['known_recall@5'] == pytest.approx(2/3)
    assert result['known_hit@5'] == 1
    assert result['all_known_hit@5'] == 0
    assert ranking_metrics(['a','b'], ['a','b'])['all_known_hit@5'] == 1
    assert result['mrr@40'] == 1
    assert ranking_metrics(['x'], ['a'])['mrr@40'] == 0
    with pytest.raises(ValueError):
        ranking_metrics([], [])


def test_channels_cannot_vote_twice_for_duplicate_id():
    assert rrf([['a', 'a', 'b'], ['b']])[0] == 'b'
