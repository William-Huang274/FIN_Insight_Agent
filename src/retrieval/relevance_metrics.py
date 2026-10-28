"""Graded main-result metrics with explicit judgment coverage and pool limits."""
from math import log2


def ranking_metrics(ranked, judgments, *, k=10):
    if k<=0 or len(ranked)!=len(set(ranked)):
        raise ValueError('relevance_metric_invalid_ranking')
    if any(type(g) is not int or not 0<=g<=3 for g in judgments.values()):
        raise ValueError('relevance_metric_invalid_grade')
    page=ranked[:k]; grades=[judgments.get(n) for n in page]
    unknown=sum(g is None for g in grades); relevant=sum(g is not None and g>=2 for g in grades)
    dcg=sum((2**g-1)/log2(i+2) for i,g in enumerate(grades) if g is not None)
    ideal=sum((2**g-1)/log2(i+2) for i,g in enumerate(sorted(judgments.values(),reverse=True)[:k]))
    return {'k':k,'returned':len(page),'judged':len(page)-unknown,'unjudged':unknown,
        'precision':relevant/k if not unknown else None,
        'precision_bounds':[relevant/k,(relevant+unknown)/k],
        'pooled_graded_ndcg':dcg/ideal if not unknown and ideal else None,
        'pooled_recall':relevant/sum(g>=2 for g in judgments.values()) if not unknown and any(g>=2 for g in judgments.values()) else None,
        'ideal_scope':'judged_pool_not_exhaustive_corpus',
        'all_equivalent_evidence_recall':None,
        'denominator':'fixed_k_missing_results_count_as_empty_slots',
        'relevant_grade_minimum':2}
