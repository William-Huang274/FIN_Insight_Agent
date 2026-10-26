from copy import deepcopy
import pytest
from scripts.engineering.retrieval_label_review import validate_heldout_label_reviews


def data():
    anchor={'source_id':'s','chunk_id':'c','body_sha256':'a'*64,'quote':'Gross capacity per day: 2 Bcf.'}
    return {'evaluation_role':'independent_source_first','questions':[{'id':'q','split':'heldout',
        'evidence':[anchor], 'label_review':{'status':'reviewed','reviewer':'synthetic-reviewer',
        'coverage_attestation':'all_question_requirements_checked_against_originals',
        'requirements':[{'id':'unit','description':'Time denominator',
                         'citations':[{**anchor,'quote':'per day'}]}]}}]}


def test_reviewed_requirements_are_bound_to_original_label_quote():
    validate_heldout_label_reviews(data(),'heldout')


@pytest.mark.parametrize('change,error',[
    (lambda q:q['label_review'].update(status='source_checked'),'review_incomplete'),
    (lambda q:q['label_review'].update(requirements=[]),'requirements_invalid'),
    (lambda q:q['label_review']['requirements'][0]['citations'][0].update(quote='per year'),'not_bound'),
    (lambda q:q['label_review']['requirements'][0]['citations'][0].update(source_id='other'),'not_bound'),
    (lambda q:q['label_review']['requirements'][0]['citations'][0].update(body_sha256='b'*64),'not_bound'),
    (lambda q:q['evidence'].append({**q['evidence'][0],'chunk_id':'unreviewed'}),'unreviewed_evidence'),
])
def test_incomplete_or_wrong_review_cannot_admit_holdout(change,error):
    value=deepcopy(data());change(value['questions'][0])
    with pytest.raises(ValueError,match=error):validate_heldout_label_reviews(value,'heldout')


def test_development_and_historical_records_do_not_claim_independent_review():
    validate_heldout_label_reviews({'evaluation_role':'independent_source_first'},'development')
    validate_heldout_label_reviews({'evaluation_role':'historical_regression'},'heldout')
