from copy import deepcopy
import pytest
from scripts.engineering.retrieval_fact_annotation import normalize_question,validate_annotation,annotation_digest


def question():
    c={'source_id':'s','chunk_id':'c','body_sha256':'h','quote':'December 31, 2025 Cash 100 million'}
    return {'id':'q','family':'f','query':'cash?','evidence':[c],
      'label_review':{'reviewer':'fixture','requirements':[{'id':'cash','citations':[c]}]}}


def test_normalization_never_invents_periods_units_or_review():
    q=question();a=normalize_question(q)
    validate_annotation(a)
    assert a['facts'] is None and a['review_level']=='clause_reviewed'
    with pytest.raises(ValueError,match='no_automatic_upgrade'):validate_annotation(a,require_typed=True)
    assert annotation_digest([a])==annotation_digest([deepcopy(a)])


def test_typed_values_units_and_period_are_source_bound():
    q=question();q['fact_review']={'status':'reviewed','entity':'Company','source_id':'s','source_digest':'v',
      'unit':'million','counterclaim':'100 billion','why_invalid':'Original says million',
      'bindings':[{'measure':'cash','entity_scope':'consolidated','display_value':'100','unit':'USD million',
         'period':{'kind':'instant','value':'2025-12-31','meaning':'balance_as_of'},
         'evidence_quote':q['evidence'][0]['quote'],'unit_quote':'million','period_quote':'December 31, 2025'}]}
    a=normalize_question(q);validate_annotation(a,require_typed=True)
    for key,value in [('display_value','999'),('unit_quote','billion'),('unit','USD billion'),('evidence_quote','invented'),('period_quote','December 31, 2024')]:
        bad=deepcopy(a);bad['facts']['bindings'][0][key]=value
        with pytest.raises(ValueError):validate_annotation(bad,require_typed=True)
