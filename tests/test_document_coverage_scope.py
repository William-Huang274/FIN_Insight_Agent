from retrieval.organization_search_needs import compile_needs, select_coverage
from sec_agent.research_foundation.organization_query_plan import document_constraint_states, select_planned


def test_recall_preserves_unknown_catalog_but_reports_its_uncertainty():
    plan={'policy':'conservative.v5','constraint':{'form':'10-K','annual_report_year':'2025'}}
    metadata={'target':{'form':'10-K','calendar_annual_year':'2025'},
              'unknown':{}, 'old':{'form':'10-K','calendar_annual_year':'2024'}}
    assert document_constraint_states(metadata,plan)=={'target':'match','unknown':'unknown','old':'mismatch'}
    accepted,receipt=select_planned(metadata,plan)
    assert accepted=={'target','unknown'}
    assert receipt['unknown_sources_retained']==1


def test_old_unknown_filing_dated_fact_cannot_jump_a_requested_filing_answer():
    plan={'policy':'conservative.v5','constraint':{'form':'10-K','annual_report_year':'2025'}}
    needs=compile_needs('Cash and cash equivalents at 2025-12-31 and 2024-12-31',plan)
    metadata={'target':{'form':'10-K','calendar_annual_year':'2025'},'old-release':{}}
    rows=[{'node_id':'target','parent_document_id':'target','content':'Cash and cash equivalents | 2025 | 2024 | 12 | 10',
           'source_structure':{'period_evidence':[]}},
          {'node_id':'old','parent_document_id':'old-release','content':'Cash and cash equivalents at December 31, 2024 was 10',
           'source_structure':{'period_evidence':[{'concept':'cash_equivalents','period':{'kind':'date','value':'2024-12-31'}}]}}]
    lanes=[{'candidate_ids':['old','target']} for _ in needs['needs']]
    selected,receipt=select_coverage(rows,needs,lanes,metadata)
    assert selected[0]['node_id']=='target'
    assert receipt[1]['period_matches']['old']=='match'
    assert receipt[1]['document_constraint_states']['old']=='unknown'
    # The same original fact remains useful for an unqualified date query.
    needs.pop('document_query_plan')
    selected,_=select_coverage(rows,needs,lanes,metadata)
    assert [r['node_id'] for r in selected]==['target','old']


def test_proven_matching_document_can_still_supply_a_missing_period():
    plan={'policy':'conservative.v5','constraint':{'form':'10-K'}}
    needs=compile_needs('Cash and cash equivalents at 2024-12-31',plan)
    rows=[{'node_id':'generic','parent_document_id':'d','content':'Cash and cash equivalents are liquid investments',
           'source_structure':{'period_evidence':[]}},
          {'node_id':'fact','parent_document_id':'d','content':'Cash and cash equivalents at December 31, 2024 was 10',
           'source_structure':{'period_evidence':[{'concept':'cash_equivalents','period':{'kind':'date','value':'2024-12-31'}}]}}]
    selected,_=select_coverage(rows,needs,[{'candidate_ids':['generic','fact']}],{'d':{'form':'10-K'}})
    assert selected[0]['node_id']=='fact'
