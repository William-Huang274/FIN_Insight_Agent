import pytest

from scripts.data_retrieval.audit_relationship_samples import audit
from sec_agent.research_foundation.research_library import ResearchLibrary
from test_research_library import publish


def test_source_span_audit_distinguishes_missing_edge_and_terms(tmp_path):
    _,path,manifest=publish(tmp_path);lib=ResearchLibrary(path)
    quote='A announced supply to B. Contract is prospective.'
    sample={'id':'s','source_id':'DOC','parent_id':'PASSAGE::p','start':0,'end':len(quote),'quote':quote,
        'expected_edges':[
            {'id':'supply','subject':'A','object':'B','predicates':['supply'],'qualifiers':{'not_delivered':True}},
            {'id':'wrong-terms','subject':'A','object':'B','predicates':['supply'],'qualifiers':{'completed':True}},
            {'id':'missing','subject':'C','object':'B','predicates':['supply']}],
        'reviewed_edges':[{'edge_id':'AB','supported':True}]}
    annotations={'library_sha256':manifest['sha256'],'samples':[sample]}
    result=audit(lib,annotations)
    assert [r['state'] for r in result['outcomes']]==['matched','qualifier_or_status_gap','not_in_reviewed_graph']
    assert result['sample_recall']==pytest.approx(1/3) and result['sample_precision']==1
    sample['end']-=1
    with pytest.raises(ValueError,match='span_mismatch'):audit(lib,annotations)
