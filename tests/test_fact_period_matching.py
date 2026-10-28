from retrieval.fact_period_matching import prose_periods,table_periods,markdown_tables,query_period,match_period
from retrieval.organization_search_needs import compile_needs,select_coverage


def test_prose_balance_authorization_and_expiry_have_different_roles():
    text=('On January 30, 2025, the Board authorized a $1.5 billion repurchase program, '
          'to expire on January 30, 2028. At September 26, 2025, $1.22 billion remained under the repurchase authorization.')
    observed=prose_periods(text)
    assert {(o['role'],o['period']['value']) for o in observed}=={
        ('authorization_event','2025-01-30'),('expiration','2028-01-30'),('balance_as_of','2025-09-26')}
    assert all(text[o['source_char_start']:o['source_char_end']]==o['quote'] for o in observed)
    need={'concept':'repurchase_authorization'}
    assert match_period({'content':text},need,query_period('截至2025年9月26日回购余额'))=='match'
    assert match_period({'content':text},need,query_period('截至2025年1月30日回购余额'))=='other_observed_period'


def test_uncertain_and_publication_periods_do_not_become_fact_periods():
    for query in ['2025年现金','In the 2025 annual report, cash','FY2025 Q1 cash','Compare cash as of 2024-12-31 and 2025-12-31']:
        assert query_period(query)['kind']=='unknown'
    assert query_period('FY2025 capital expenditures')=={'kind':'fiscal_year','value':'2025'}
    assert not prose_periods('Published January 30, 2026. Cash and cash equivalents were $100 million.')
    assert not prose_periods('Fiscal 2025 cash and cash equivalents.')
    assert not prose_periods('At December 31, 2025 and December 31, 2024 cash and cash equivalents were 100 and 90.')
    assert not prose_periods('At December 31, 2025 and 2024 cash and cash equivalents were 100 and 90, respectively.')
    assert not prose_periods('During first quarter fiscal 2025 capital expenditures were 20.')
    assert not prose_periods('In our fiscal 2025 report cash and cash equivalents were $100 million.')
    assert not prose_periods('A forecast at December 31, 2025 indicated that cash and cash equivalents might reach $100 million.')
    assert not prose_periods('Cash and cash equivalents as of December 31, 2025:\n[TABLE: original]\n100\n[/TABLE]\nA separate 20 percent fee.')


def test_combined_liquidity_is_not_proof_of_cash_equivalents_alone():
    from retrieval.fact_period_matching import balance_concepts
    for text in ['cash, cash equivalents and marketable securities',
                 'cash and cash equivalents and short-term investments',
                 '现金及现金等价物和短期投资']:
        assert 'cash_equivalents' not in balance_concepts(text)
    assert 'cash_equivalents' in balance_concepts('Cash and cash equivalents')
    assert not prose_periods('As of December 31, 2025, cash, cash equivalents and marketable securities were $5 billion.')


def test_period_comparisons_and_fiscal_quarters_keep_explicit_identity():
    from retrieval.fact_period_matching import query_period_requirements
    assert query_period_requirements('Cash as of 2024-12-31 and 2025-12-31')['targets']==[
        {'kind':'date','value':'2024-12-31'},{'kind':'date','value':'2025-12-31'}]
    assert query_period_requirements('Revenue from 2025-01-01 to 2025-06-30')['targets']==[
        {'kind':'duration','start':'2025-01-01','end':'2025-06-30'}]
    assert query_period_requirements('Revenue FY2025 Q1')['targets']==[
        {'kind':'fiscal_quarter','fiscal_year':'2025','quarter':1}]
    assert query_period_requirements('Published 2025-06-30, cash disclosed on 2025-07-01')['targets']==[]


def test_fact_entity_must_match_an_explicit_identifier_before_period_preference():
    period={'kind':'date','value':'2025-12-31'}
    evidence={'concept':'cash_equivalents','role':'balance_as_of','period':period,
        'entity':'00000123','entity_scheme':'http://www.sec.gov/CIK'}
    row={'content':'Cash 10','source_structure':{'period_evidence':[evidence]}}
    need={'concept':'cash_equivalents','owner':{'issuer_id':'I::alpha'}}
    assert match_period(row,need,period)=='unknown'
    need['owner']['fact_entity_identifiers']=[{'identifier':'456','scheme':'http://www.sec.gov/CIK'}]
    assert match_period(row,need,period)=='unknown'
    need['owner']['fact_entity_identifiers']=[{'identifier':'123','scheme':'https://www.sec.gov/CIK'}]
    assert match_period(row,need,period)=='match'
    evidence['entity_scheme']='different-identifier-system'
    assert match_period(row,need,period)=='unknown'


def test_markdown_headers_bind_columns_not_document_year():
    text='Published 2026\n| Metric | 2025-12-31 | 2024-12-31 |\n| --- | --- | --- |\n| Cash and cash equivalents | 100 | 90 |\n'
    observed=table_periods(text,markdown_tables(text))
    assert {(o['quote'],o['period']['value']) for o in observed}=={('100','2025-12-31'),('90','2024-12-31')}
    for item in observed:assert text[item['source_char_start']:item['source_char_end']]==item['quote']
    # Ragged/merged cells and bare years are not guessed.
    assert not markdown_tables(text.replace('| 100 | 90 |','| 100 |'))
    assert not table_periods(text.replace('2025-12-31','2025').replace('2024-12-31','2024'),markdown_tables(text.replace('2025-12-31','2025').replace('2024-12-31','2024')))


def test_ordinary_html_multilevel_headers_and_duration_abstention():
    from retrieval.source_table_periods import build_overlay
    from hashlib import sha256
    from retrieval.source_table_periods import MARKER
    raw=b'<html><table><tr><th></th><th colspan="2">December 31</th></tr><tr><th>Metric</th><th>2025</th><th>2024</th></tr><tr><td>Cash and cash equivalents</td><td>100</td><td>90</td></tr></table></html>'
    # Use the parser's public replay to verify exact archived coordinates.
    body=MARKER+'\n | December 31\nMetric | 2025 | 2024\nCash and cash equivalents | 100 | 90\n[/TABLE]'
    overlay=build_overlay(raw,raw_sha256=sha256(raw).hexdigest(),source_digest=sha256(body.encode()).hexdigest())
    observed=table_periods(body,overlay['tables'])
    assert {(o['quote'],o['period']['value']) for o in observed}=={('100','2025-12-31'),('90','2024-12-31')}
    assert all(body[c['source_char_start']:c['source_char_end']]==c['quote'] for o in observed for c in o['header_components'])
    text='| Metric | Year ended December 31, 2025 |\n| --- | --- |\n| Capital expenditures | 100 |'
    assert not table_periods(text,markdown_tables(text))
    for header,label in [('May 18 through December 31, 2023','Cash and cash equivalents'),
                         ('September 26, 2025','Net cash provided by operating activities'),
                         ('September 26, 2025','Common stock repurchases'),
                         ('December 31, 2025','Cash and cash equivalents at beginning of period')]:
        text=f'| Metric | {header} |\n| --- | --- |\n| {label} | 100 |'
        assert not table_periods(text,markdown_tables(text))


def test_matching_preserves_unknown_candidates_and_legacy_order():
    query='Cash and cash equivalents as of December 31, 2025'
    rows=[{'node_id':'old','parent_document_id':'doc','content':'As of December 31, 2024, cash and cash equivalents were $90 million.'},
          {'node_id':'unknown','parent_document_id':'doc','content':'Cash and cash equivalents were $500 million.'},
          {'node_id':'current','parent_document_id':'doc','content':'As of December 31, 2025, cash and cash equivalents were $100 million.'}]
    plan={'policy':'conservative.v5','constraint':{}}
    needs=compile_needs(query,plan)
    lanes=[{'need_id':n['id'],'candidate_ids':['old','unknown','current']} for n in needs['needs']]
    ranked,receipts=select_coverage(rows,needs,lanes,{})
    assert [r['node_id'] for r in ranked]==['current','old','unknown']
    assert receipts[0]['period_matches']=={'old':'other_observed_period','unknown':'unknown','current':'match'}
    legacy=compile_needs(query,{**plan,'policy':'conservative.v4'})
    assert select_coverage(rows,legacy,lanes,{})[0]==rows
    # No positive match: do not silently promote an arbitrary lexical anchor.
    assert select_coverage(rows[:2],needs,lanes,{})[0]==rows[:2]


def test_organization_v5_reads_current_scope_on_cache_hit(tmp_path,monkeypatch):
    import pytest
    from test_organization_candidate_index import prepared,query
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    nav,reader,state,_,_=prepared(tmp_path,monkeypatch)
    request=query(organization_query_planning='conservative.v5')
    result=nav.navigate(request)
    assert result.items[0]['retrieval']['search_needs']['period_policy']=='explicit-fact-periods.v1'
    assert nav.navigate(request).items[0]['retrieval']['response_cache_hit']
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(request)
