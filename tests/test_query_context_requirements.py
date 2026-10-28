from retrieval.query_context_requirements import context_requirements
from retrieval.organization_search_needs import compile_needs


def test_explicit_context_requests_not_business_units_or_unknown_topics():
    assert context_requirements('2024-12-31? Retrieve the two date columns')==['table_period_headers']
    assert context_requirements('the stated units')==['measurement_units']
    assert context_requirements('the scale to check these claims')==['measurement_units']
    assert context_requirements('请提供原文计量单位以及页码')==['measurement_units','original_citations']
    for text in ['units shipped','business units','units','customer concentration and page references','measurement units sold']:
        assert not context_requirements(text)


def test_period_comparison_does_not_make_unit_instructions_extra_financial_needs():
    plan={'policy':'conservative.v5','constraint':{},'issuer_mentions':[]}
    query='Cash and cash equivalents at 2025-12-31 and 2024-12-31? Retrieve the two date columns and the stated units.'
    needs=compile_needs(query,plan)
    assert len(needs['needs'])==2
    assert {n['concept'] for n in needs['needs']}=={'cash_equivalents'}
    assert {role for r in needs['context_requirements'] for role in r['roles']}=={'table_period_headers','measurement_units'}
    unknown=compile_needs('Cash equivalents and customer concentration',plan)
    assert any(n['concept'] is None and 'customer' in n['text'] for n in unknown['needs'])


def test_counterclaim_stays_in_full_query_without_creating_phantom_business_need():
    plan={'policy':'conservative.v5','constraint':{},'issuer_mentions':[]}
    query='A summary assigns a cash figure to 2025-12-31 and labels the amounts as billions. Find the cash and cash equivalents row and the scale to check these claims.'
    result=compile_needs(query,plan)
    assert len(result['needs'])==1
    assert result['needs'][0]['text']==query
    assert {r for entry in result['context_requirements'] for r in entry['roles']}=={'assertion_to_verify','measurement_units'}


def test_unmapped_business_topic_coverage_preserves_reranker_not_bm25_order():
    from retrieval.organization_search_needs import select_coverage
    needs={'policy':'organization-financial-needs.v2','needs':[
        {'id':'one','owner':None,'concept':'revenue','lexical_routes':[['revenue']]},
        {'id':'two','owner':None,'concept':None,'lexical_routes':[['widgets']]}]}
    rows=[{'node_id':'answer','parent_document_id':'doc','content':'Revenue and widgets result'},
          {'node_id':'boilerplate','parent_document_id':'doc','content':'Widgets risk statement'}]
    lanes=[{'candidate_ids':['answer']},{'candidate_ids':['boilerplate','answer']}]
    selected,_=select_coverage(rows,needs,lanes,{})
    assert selected[0]['node_id']=='answer'
