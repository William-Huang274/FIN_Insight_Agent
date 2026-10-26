from hashlib import sha256
import pytest
from scripts.engineering.retrieval_evidence_sets import validate_requirements,requirement_metrics


def test_alternative_requires_both_passages_and_preserves_revision():
    originals={n:dict(parent_document_id='same',raw_body_sha256='revision',content=text)
               for n,text in [('a','Closed in May, paid units, additional units conditional.'),
                              ('b','Closed in May, paid units.'),('c','Additional units conditional.') ]}
    def label(n):return dict(node_id=n,quote=originals[n]['content'],
                            content_sha256=sha256(originals[n]['content'].encode()).hexdigest())
    requirements=[dict(id='transaction',statement='Date, payment form and condition',
        review_basis='Synthetic equivalent source paragraphs',alternatives=[[label('a')],[label('b'),label('c')]])]
    validate_requirements(requirements,originals)
    assert requirement_metrics(['b','c'],requirements)['all_requirements@5']
    assert not requirement_metrics(['b'],requirements)['all_requirements@5']
    assert requirement_metrics(['a'],requirements)['all_requirements@5']
    originals['c']['raw_body_sha256']='other'
    with pytest.raises(ValueError,match='revision_mismatch'):validate_requirements(requirements,originals)
