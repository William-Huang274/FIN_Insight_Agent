from retrieval.graph_query_plan import graph_seeds
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


def request(query,**kwargs):
    return SourceDocumentRequest(source_space='organization',operation='search',query=query,
        organization_query_planning='conservative.v5',**kwargs)


def test_only_explicit_or_resolved_relationships_seed_graph():
    plan={'constraint':{'issuer_id':'COMPANY::acme'}}
    assert graph_seeds(request('Acme suppliers'),plan)==(['COMPANY::acme'],'resolved_query_issuers')
    assert graph_seeds(request('Acme 现金余额'),plan)[0]==[]
    assert graph_seeds(request('Acme 供应商'),{})[0]==[]
    assert graph_seeds(request('cash',entity_id='EXACT'),plan)==(['EXACT'],'explicit_entity')


def test_multiple_resolved_owners_preserved_without_name_guessing():
    plan={'constraint':{'issuer_union':[{'issuer_id':'A'},{'company_names':['Unknown']},
                                        {'issuer_id':'B'},{'issuer_id':'A'}]}}
    assert graph_seeds(request('A and B customer relationships'),plan)[0]==['A','B']
