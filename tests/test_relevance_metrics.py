import pytest
from retrieval.relevance_metrics import ranking_metrics


def test_one_correct_result_does_not_mean_precise_top_ten():
    ranked=[str(i) for i in range(10)];q={n:3 if n=='1' else 0 for n in ranked}
    r=ranking_metrics(ranked,q)
    assert r['precision']==.1 and r['pooled_graded_ndcg']==pytest.approx(1/1.584962500721156)
    assert r['all_equivalent_evidence_recall'] is None


def test_unknown_is_not_negative_and_supplements_cannot_change_primary_metrics():
    r=ranking_metrics(['a','b'],{'a':3})
    assert r['precision'] is None and r['precision_bounds']==[.1,.2]
    assert r['pooled_graded_ndcg'] is None
    assert ranking_metrics(['a'],{'a':3})['precision']==.1


def test_duplicate_results_and_invalid_judgments_are_rejected():
    with pytest.raises(ValueError):ranking_metrics(['a','a'],{'a':3})
    with pytest.raises(ValueError):ranking_metrics(['a'],{'a':True})
